# The Training Studio desk

Conversation can create, inspect and save the same desk records with `studio desk create/show/context/submit/save`. It needs no browser or nested assistant. Requested scope is explicit and finite; a teaching-plan-only request creates no broader materials. Checked acceptance leaves materials Draft. `studio desk take/scope/handoff` are explicit checked ownership and scope changes; restarts and page visits leave conversation-owned work alone. `studio desk answer` records only actual current look/design answers. The existing `training.py desk` command still serves the page.

The desk is where you read, change and finish a new training as Training Studio makes it. Start with **New training**: describe the learning goal and audience, choose materials and research sources, then check the summary and start. You can leave and return while work continues. Progress shows what is being made, time and cost, and anything that needs you; pause, resume or stop work from the run.

## Start in three short pages

**New training** has Goal and audience, Sources and questions, then Outputs and review.
Back and Next keep your answers and source choices. The last page describes the next
operation and the selected materials, with assistant limits under a disclosure.
**Start** creates the training and begins work. Moving between pages starts no work.

Your unfinished form is saved privately on this computer for its configured workspace,
including its current page, captured source identity and selected Library revisions.
Reload returns to an open form; **Save and close** leaves it closed until you reopen
New training. **Discard draft** asks once, then removes only the unfinished form.
Captured sources, Library documents and existing trainings are kept. A save conflict
between tabs asks you to preserve your unsaved answers and reload the saved version.

## Approve the outline, then research and build

New runner trainings first run one bounded **Quick scan**, with no external searches.
The scan gets short excerpts and proposes sections, objectives and research questions.
It is provisional and supplies no teaching evidence. At **Review the training outline**,
edit a title, put one objective or question per line, remove a section, or add your own.
Questions typed on the form remain separately editable. **Save outline** keeps edits
without a model job; reload restores the saved version. Unsaved edits are marked and
protected by a browser navigation warning. Conflicting inputs never overwrite your edits.
**Research approach, scan and limits** expands the process detail while the source
scope and approval consequence stay visible. Incomplete-scan warnings stay visible too.

**Approve outline & research** approves that exact edited scope. Only retained sections
become research items, with your additional questions included. Up to three areas run in
parallel within the saved source and round limits. Combining and an independent
check still cover the whole dossier. An assistant then decides what the check flags, and the training carries on: it keeps a
minor point as written, adds a warning where the doubt is real, and leaves out only a
claim that a source directly contradicts and that is very important to what is taught.
When sources disagree, the newer document usually wins. Each choice and its reason is in
the evidence under **Automatic decisions and independent-check notes**, which says the
creator has not reviewed them; it is never recorded as your decision. If the assistant
hands nothing back, every flagged item is included with a warning. Tick **Decide flagged
research myself** on the form and unresolved flags become your Include / Include with
warning / Exclude choices instead; save them and explicitly continue. Trainings already
started keep your decision. Excluded findings also omit dependent content. The teaching plans and selected materials
then use your approved scope and accepted research, with no second topics approval.
A deck is drawn straight from its words, with no stop: change either on the desk.
Tick **Approve the slide text before the deck is drawn** on the form to keep that
approval for one training. Mark ready keeps its existing role.

New trainings prioritize readable output: each level's plan, guide and brief, then
practice and Yoodli across levels, then decks. Selected inputs still precede the
materials that use them. This changes order, not the number of concurrent assistants.
Saved runs keep their recorded order and scoped updates keep their existing holds.
See the [flow and task map](../../../docs/design/create-training-task-flow.md).

The working desk shows one current step, the number of available drafts and the next
material. **Writing** means an observed worker is producing that material; **Queued**
means it is waiting, with the reason shown when opened. A previous draft remains
downloadable while its update waits, but it is not newly ready. Expand **Activity**
and **Time so far** for details; the latest reported activity stays visible. Saved
research choices are folded away with a reminder that your choices and independent-check notes are saved.

The overall workflow map stays above the desk, including at approval and after
generation finishes. Select a stage to expand its detail. **Materials** groups
Plans, guides & briefs, Practice & Yoodli, and Slides when selected. Each saved
item has **Open**; queued updates still identify the previous draft. Branches report
their own waits, so a slide decision cannot hide a guide already available.
**Your review** distinguishes reviewable drafts from materials you marked ready.
Counts cover the materials currently listed; practice items appear as level plans
are saved. Research detail shows observed phase and available area/section counts.
**Creator accepted** records your decision. Choose **Include** for ordinary content, **Include with warning** for a visible note, or **Exclude**. Independent-check notes stay in the evidence; warnings appear only where requested.

Stage selection, opening a draft and polling start no assistant work. Keyboard focus
and the selected detail survive refreshes. Older runs show Research before Teaching
plan where applicable; conversation-only desks show retained Materials and Your review
without invented execution history. Another computer's work is labeled saved progress.

A scan time cap leaves an editable incomplete outline, without escalation or an automatic
second author. Stop keeps a completed or fallback outline; Resume training returns to its review.
The Activity log records the scan and its model/effort separately from deeper work.

Older saved trainings keep the following researched-topics flow. A stopped runner desk
before a research report or teaching plan can choose **Plan before research**. Its preview
shows what is kept and replaced. Explicit adoption preserves sources, spending, activity
and the unfinished private research case as history; Resume training starts the scan. It makes no
claim that unfinished evidence is independently checked. Past-research work stays as saved.

## Older researched-topics flow

These saved trainings first research and plan what to teach. **Here’s what this training will
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

On a phone the desk keeps out of the way of what you read. The toolbar is one row with the title, the one filled action (such as **Mark level ready**, which marks the whole level; each card keeps its own **Mark ready**) and **More**, which holds Download, Google Doc and Finishing. The material and section tabs are one row that scrolls sideways, and choosing one brings what it shows to the top of the screen. While a sheet is open, Tab and Shift+Tab go round its own controls only.

## The deck

The deck card shows one slide at a time. Choose a slide in **Slide to review**; slides with review suggestions are marked. Expand **Edit slide text and speaker notes** to change its words. Detailed review notes stay collapsed on the deck card. You can edit slide words and speaker notes, choose a look, and request changes to a slide or the whole deck. A slide note redraws its section; other slides are kept. Review findings are proposals: **Apply fix to this slide** requests a change at the displayed price, while **Dismiss suggestion** records that you read the finding. There are no automatic repair rounds on the desk. A grave finding still blocks **Mark ready**, even if skipped.

Harness Slides 0.16 requires your explicit approval of its design questions when a word change affects an approved drawing. The desk shows the questions and submits your answers. A proposal alone does not approve the change. If the change cannot be checked or rendered, the previous deck remains. Speaker notes do not require this design approval.

## Holds and updates

When you change an input, a dependent material can be held because it was built from an earlier version. Choose **Update** to make it from the current input, or **Keep as it is** to retain it. Update or keep an upstream hold first. Where offered, choose a scope for an update, or update a chain of dependent materials. The desk shows the estimated price before you request work. Stopping updates leaves the remaining materials held; a step already working may finish. Materials Training Studio does not remake can be kept or changed by you.

## Add a source

Use **Add a source** to add documents after research. The desk shows the price before you update the research. New or changed findings are marked, and dependent materials may be held for your decision. A change already in progress may need to finish or stop first. Existing documents stay in the training.

**Add from library**, in the same sheet, takes documents already kept in the Document Library without uploading them again. They wait, unread, until you choose **Update the research**, and start nothing before then. A training researched from the public web reads your documents too from then on, as the sheet says first.

## Change settings

**Change settings** changes what a training was started with without starting over. It sits beside **Try again** on the card that says the training has stopped, and in the desk's toolbar (the **More** menu on a phone), whenever the run is not working: stopped, failed, waiting for you, or paused with nothing in hand. It is never offered while an assistant is working; stop the training first. A finished training keeps its settings; start a new one to make it again with others.

It opens one scrolling form filled with the saved settings, grouped into the teaching goal, outputs and research: what it teaches, who it is for, how long it should take and what it is for; the levels, the brief and the deck, its brand and how it is used; and what research reads, in the same source panel as the start, with **Search for additional external sources** and your approved sites, and the research questions. The title stays as it is. A part that cannot be changed safely says why instead: a deck that has been begun, a level with work in it, a training without levels, or research made with the earlier research workflow that still holds its unfinished draft. When the source panel cannot open what research reads, for example because its captures stay on the computer that started the training, what research reads is shown as it is and the rest of the form can still be changed.

**Review the change** says what the change does before anything is saved:

- **Research that has not been accepted into a finished report is discarded**, and the research is planned again with the new settings, when you change the topic, audience, purpose, research questions, sources, external search or sites. The review says how many research tries that discards and the time and money they took, from the run record, and that it cannot be undone; the button then reads **Discard and save**. Other changes keep the research plan. Research not yet accepted then starts again, because the research is given every setting on the form; research made with the earlier research workflow carries on from its draft instead, and a change of the deck's brand, delivery or walkthrough alone leaves research to carry on. A stop that is not about research keeps its own action, such as **Give it more time and try again**, and Continue after a stop for time gives each step twice the time, as that action would, and says so.
- **A finished research report is kept** unless you tick **Research again with the new settings**, which researches again only when research is given something new. If you approved the topics and teaching plan, a change of the answers or the levels asks you to check it again. What depends on a change is held on the desk for you to **Update** or **Keep as it is**, as with any other change of input; a material you marked ready is never changed without your say. An added level, or another kind of brief, leaves the blueprints as they are and makes only what is new.

Scroll inside the Change settings form to reach Research and its review and cancel buttons. The page behind it stays still. Tab stays within the dialog; Escape closes it and returns focus to Change settings.

**Save the change** writes intake.md, the training's records and its research inputs together, and records "change the training's settings: …" in the training's history. Then the training waits: nothing starts until you press **Continue**. **Cancel** changes nothing. A form opened before something else changed the training is refused; open Change settings again.

## Use the current model settings

A training saves the model and reasoning level it uses for each kind of work (Quick, Research, Combining, Checking, Writing and Fixing) when it starts, so a later change in **Settings → Advanced → Models and reasoning** reaches only new trainings. **Use the current model settings**, beside **Change settings** on the stop's card and in the desk's toolbar, brings a stopped training up to date: it lists each kind whose model or reasoning would change, before and after (for example, "Research: high reasoning → medium reasoning"), and changes nothing until you press **Use these models**. Only the jobs still to run use them: finished work is kept, and what stopped the training stays, with its own button (**Try again**, **Give it more time**, **Carry on**). It works on any stopped training of yours, including one started before Change settings existed, and it is recorded as "use the current model settings: …" in the training's history. The [shared setup guide](../../../docs/shared-setup.md#models-by-kind-of-work) says what runs on each kind.

## Mark ready and Finishing

Under the level tabs, one line says how many of the level's materials are ready, still to write, drafts to mark ready, or need attention or a decision. A material is ready on its own; a level is complete once all of its materials are, and downloads and Google Docs stay optional. The fuller readiness explanation is under **About Ready and delivery** below the material, so the material comes first. While a deck's slide text waits for you, its tab says **Needs your text approval** and **Review slide text** takes you to it; materials not written yet say **Not written yet**, never Writing, while nothing works on them. Time so far is a detail you open; elapsed time is never an estimate of what is left.

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

While research and every later job run, the progress band names each job, when it
started and what it is doing now (**Now: …**). **Show activity** opens every line it has
said so far, newest first, each with its time, and stays open as the page refreshes. The
lines are the plain sentences the runner makes of the assistant's actions, such as
"Searching the web: …" or "Reading saved source S3"; never the brief, the sources or the
assistant's raw events.

**Activity log**, at the foot of the desk and of the run screen, lists each finished
assistant job, newest first: its name, its times, how it ended (Finished, Failed,
Stopped, Out of time or Reached a limit) and its lines. It is read when you open it, while
the training works and after it finishes, fails or stops. The runner keeps it in the
training's `work/activity-log.jsonl`, which is never committed or shared, for the latest
200 jobs and 200 lines a job. A training with no log says "No activity recorded yet."

Elapsed time includes waiting and stopped time. Active time counts overlapping
workers once; total assistant time adds their durations. Incomplete older timing
history is identified. Existing trainings continue with their saved workflow.
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

### Choosing practice and Yoodli scenarios

When Practice scenarios or Yoodli is selected, **Let AI choose** is the default.
**Define scenarios** accepts one short description per scenario (up to 300
characters). Add or remove descriptions; AI supplies roles, dialogue, goals and
evaluation criteria, adapted to every selected level. The same intent follows the
scenario into its Yoodli fields. Existing authored scenarios are kept.

The private intake saves your descriptions across reloads and mode switches.
After starting, use **Change settings** while stopped, review the change and save.
Scenario-only changes keep collected research and mark affected materials out of
date; saving launches no work. Update or keep existing drafts explicitly.
