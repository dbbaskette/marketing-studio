# The Training Studio desk

Conversation can create, inspect and save the same desk records with `studio desk create/show/context/submit/save`. It needs no browser or nested assistant. Requested scope is explicit and finite; a teaching-plan-only request creates no broader materials. Checked acceptance leaves materials Draft. `studio desk take/scope/handoff` are explicit checked ownership and scope changes; restarts and page visits leave conversation-owned work alone. `studio desk answer` records only actual current look/design answers. The existing `training.py desk` command still serves the page.

The desk is where you read, change and finish a new training as Training Studio makes it. Start with **New training**: describe the learning goal and audience, choose materials and research sources, then check the summary and start. You can leave and return while work continues. Progress shows what is being made, time and cost, and anything that needs you; pause, resume or stop work from the run.

## Read and change materials

Open the training on the desk. Each level has its own plan and materials; research is shared. Open a card to read its parts. You can type in an editable part, add a note asking for a change, or select a passage and ask for a change to just that passage. Review the result as it arrives. History keeps earlier versions and lets you restore one. Your own typing is saved, and a result does not overwrite a part you changed while it was working.

Sources collects the findings and references used in the training. A guide or brief's Sources section is maintained from its citations; change references in the text instead of typing into that section. You can read the research and plan, and decide how changes should reach the materials that depend on them.

## The deck

The deck card shows its slides, words, look and review findings. You can edit slide words and speaker notes, choose a look, and request changes to a slide or the whole deck. A slide note redraws its section; other slides are kept. Review findings are proposals: **Apply** shows the price and requests a change, while **Skip** records that you read the finding. There are no automatic repair rounds on the desk. A grave finding still blocks **Mark ready**, even if skipped.

Harness Slides 0.16 requires your explicit approval of its design questions when a word change affects an approved drawing. The desk shows the questions and submits your answers. A proposal alone does not approve the change. If the change cannot be checked or rendered, the previous deck remains. Speaker notes do not require this design approval.

## Holds and updates

When you change an input, a dependent material can be held because it was built from an earlier version. Choose **Update** to make it from the current input, or **Keep as it is** to retain it. Update or keep an upstream hold first. Where offered, choose a scope for an update, or update a chain of dependent materials. The desk shows the estimated price before you request work. Stopping updates leaves the remaining materials held; a step already working may finish. Materials Training Studio does not remake can be kept or changed by you.

## Add a source

Use **Add a source** to add documents after research. The desk shows the price before you update the research. New or changed findings are marked, and dependent materials may be held for your decision. A change already in progress may need to finish or stop first. Existing documents stay in the training.

## Mark ready and Finishing

**Mark ready** records your approval of a material. You can also mark a level ready; the desk stops at the first material that needs attention. Settle holds, grave deck findings and other blocking checks first. A later edit makes the material a draft again. Once all requested materials are ready, Training Studio writes the index. Requested copies follow readiness; a guide or brief can also be sent to a Google Doc from the desk. You can look for changes in Google Docs and bring them back, resolving a conflict if both versions changed.

**Finishing** offers checks and proposals for the training. Review each proposal and choose Apply, Edit or Skip. A proofread fix may request work; other findings can open a note for you to edit. Applied changes keep a version in History. Local checks create proposals without starting a job. When you request an AI check, it runs work to produce proposals; each proposal waits for your decision.

## Working with teammates and older trainings

In a shared workspace, one computer drives a training at a time. A teammate can read what was shared and explicitly take over when needed. Your unshared work is kept aside when a takeover requires it. Share before leaving the desk so teammates can see your work.

Trainings started before the desk keep their original review flow. Once a saved training is finished and nothing is waiting, **Open on the desk** brings it to the desk. Existing person-approved material stays ready where applicable; other material may return as a draft for your decision. Opening it again does not create another copy.

Conversation-owned work supports explicit person Mark ready through the main desk or checked `studio desk ready`, without runner handoff or jobs. Retained helper-page decisions and approval-mode changes refuse conversation ownership under the shared write guard. `studio desk return-delivered` previews and losslessly sets aside an undelivered local deck in History, restoring proven delivered active state or prior absence; it does not publish or invent approval.
