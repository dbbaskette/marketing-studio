# Piece 1, workflow fixes: design

**Date:** 2026-10-26, at main cc53056. **Owner's words:** "Lets apply our UI changes to blog
studio to the other studios. We also need to do an audit of workflow and clean it up", and,
asked whether that meant the layout rules or the writing desk as well: "1 and 2".

This is piece 1 of `2026-10-26-workflow-audit.md`: "The broken paths and wrong copy above,
in all three studios and Marketing Studio's setup, with route tests at every review level."
It fixes paths that lose a person's work or leave them with nothing to do, and sentences
that say what the page does not do. It deletes no code (piece 2), restyles no layout
(piece 4), builds no desk (pieces 5 and 6) and removes no review level (piece 7).

Line references are to main cc53056 and were checked against the code. The findings beside
the audit hold the full evidence: `2026-10-26-workflow-audit/presentation.md` (sections 1
and 2), `training.md` (sections 1 and 2, parts A and B) and `blog-and-shared.md` (Parts A.1,
A.2, A.4 item 1, B.1 to B.3).

## Decisions for the owner

1. **A delivered PowerPoint file is shared.** Presentation Studio commits a copy of the
   delivered `.pptx` beside the deck, as Training Studio already does for its decks. Older
   deliveries stay where they are, and the page says which computer has them.
2. **Training Studio takes a document after research is planned.** It is kept, and is
   not read until the person chooses **Update the research**, which is priced first. Only a
   training that already reads documents takes one. A web-only or sites-only training still
   refuses, with a sentence that says why. Widening where research looks goes to piece 6.
3. **A change at Training's finished-materials review no longer reopens the first drafts.**
   What the change rewrites comes back to the review where it was asked for. A deck that is
   drawn again still stops at its own gate.
4. **Under Balanced, a Redesign deck stops at the look.** Balanced folds the look into the
   direction review. A Redesign deck has no outline stop, so the look stop is the direction
   review.
5. **Blog Studio's desk start asks "What do you have?" before "Sources and settings"**, as
   the writing desk spec says. Then the research and Length choices match what was brought.
   `docs/design/blog-workflows.md` changes to match.
6. **Mark as published keeps a desk blog in the team library**, as Finish does for an older
   run. The sheet says so.
7. **The library's "Start an editable blog from this file" opens the desk start** with
   the file as the draft. It no longer makes a manuscript-editor blog. Piece 2 deletes the
   server branch this leaves unused.
8. **Marketing Studio's setup and Settings save once.** The installation folders join the
   shared settings form, so one Save writes both. Blog Studio's own first run no longer asks
   for a review level, a delivery format or slide previews, because Blog Studio does not use
   them.

## What is wrong now

Ranked within each studio by what a person loses. P = `studios/presentation`, D =
`P/skills/presentation-studio/scripts/desk`, T = `studios/training`, R = `T/runner`, TA =
`T/skills/training-studio/scripts/desk/app.js`, B = `studios/blog/skills/blog-studio`, M =
`B/assets/management`, C = `core/studio_core`.

### Presentation Studio

1. **Balanced never shows the look for "Redesign, keep content".**
   - `C/deck_flow.py:61-62` hosts Balanced's direction review at `gate:outline`.
   - A Redesign deck has no `gate:outline` (`P/runner/stages.py:105-106`).
   - So `deck_flow.stops` (`:106-120`) returns False for `gate:look`, and
     `review_policy.automatic` (`C/review_policy.py:119-121`) passes it.
   - `Engine._look_policy` (`P/runner/engine.py:2250-2271`) then calls
     `look.choose_default` (`P/runner/steps/look.py:292-310`). That records "Automatic
     draft: the brand's default look, {name}, was used." (`C/deck_flow.py:85`) under
     Balanced.
   - `look.approve` (`look.py:385-386`) then writes it as `In their words: "…"`, as if the
     person had said it.
   - README.md:3 promises "Balanced brings research, the outline and the brand's looks
     together for one review, where you pick the look".
   - The form's line agrees with the bug: "Balanced: it stops for the deck"
     (`D/app.js:2906-2909`, `stopsFor` at 2886-2910).
   - Every route test runs at Step by step only. `P/tests/runner_support.py:844-845`
     patches `capture` to `'step_by_step'`, and `test_flow_routes.py:186-187` is the only
     Redesign walk.
2. **A PowerPoint delivery cannot be reached from another computer.**
   - The file is `work/deck.pptx` (`P/runner/steps/build.py:672`, `deliver.py:78`).
   - `work/` is in `gitstate.IGNORED` (`P/runner/gitstate.py:94`).
   - On a teammate's computer `_rendered` (`engine.py:3245-3250`) is False, so there is no
     **Download .pptx** (`D/app.js:5080`).
   - Yet Home and Decks say "A .pptx, to download from its own screen."
     (`D/app.js:1398`, driven by `deliver.json`'s `pptx`, which is shared).
   - Publishing tags a commit with no deck in it (`team.py:295-322`).
3. **Undo is offered when it will be refused.**
   - "Undo the last step" shows on every deck that is not working (`D/app.js:5720-5722`).
   - `gitstate.undo` (`gitstate.py:666-678`) refuses a step already shared. Sharing happens
     after each decision by default (`SHARE = ('decision', 'asked')`, `gitstate.py:92`).
   - So the sheet opens, and then says "The last step cannot be undone: only the last thing
     done, when it was this deck's and is not shared yet, can be." (`engine.py:260-261`).
   - The view carries nothing that says whether undo can be done (`Engine.view`,
     `engine.py:3083-3121`).
4. **"That’s wrong" redraws at once and has no price.**
   - In the direction review, `classifyLine` (`D/app.js:4516-4531`) sends the change on one
     click (`:4523-4524`).
   - `_reclassify` (`engine.py:2046-2067`) resets the steps and draws the outline and the
     looks again. Taking a script for material also runs the research.
   - Every other redraw says its cost first: `_redo`, `research_price` and
     `_leave_out_price` (`engine.py:3135-3165`, `2846-2850`, `2038-2044`).
5. **"Sign in on Status" points at a screen with no sign-in.**
   - The page says "Sign in on Status and Deliver to Google Slides afterwards."
     (`D/app.js:5061-5062`) and "Sign in to Google on Status to send this deck to Google
     Slides later." (`:5094-5095`).
   - `existing.NOT_READY` says "Sign in to Google on Status, under Check this computer, or
     download the file and upload it." (`P/runner/steps/existing.py:78-79`).
   - Status only checks `gcloud --version` (`P/skills/presentation-studio/scripts/computer.py:23`) and prints
     a fix line (`:155-158`).
   - The button is named **Send to Google Slides** (`D/app.js:5088`).
6. **No question can be added at the research stop.**
   - The synthesis branch of `researchPanel` leaves out `addedPart`
     (`D/app.js:4116-4134`; the queue branch has it at `:4146`).
   - The engine takes an added question: `marks.py:106-108` and
     `Researching._add_questions` (`research_steps.py:624-649`), capped at
     `PLAN_MOST = 8` for a contract run.
   - `P/docs/runner.md:57` still promises "Up to 10 questions can be added at once (a plan
     holds at most 30)".

### Training Studio

1. **A teammate's edits in a Google Doc almost never come back.**
   - "Bring the Doc's changes in" is drawn only on a conflict, or on a problem that starts
     "Someone has changed the Google Doc" (`TA:5573-5576`).
   - That problem comes only from a push (`R/copies.py:60-62`). `copies.make` skips copies
     already made (`:113`).
   - `gdocs.copy_states` says "Nothing here asks Google"
     (`T/skills/training-studio/scripts/gdocs.py:375-392`). `gdocs.status` (`:353-372`)
     can tell "remote changed", but the runner never calls it.
   - When the button does show, the local file has changed too, so the pull always ends in
     the both-changed choice (`copies.py:213-233`).
   - Headings that lost their hidden note come back as `unplaced`, and `copies.pull` drops
     them (`copies.py:235`).
   - `T/docs/runner.md:192` promises the button. `:347` says pulling "is not in the runner
     yet".
2. **No document can be added once research is planned.**
   - `Engine.supply` refuses with `SETTLED`: "The research for this training was planned
     from the documents already added, so they cannot be changed now."
     (`R/engine.py:300-301`, `3793-3794`).
   - The research stop's sheet offers only a note and "Bring the evidence up to date"
     (`TA:1368-1418`). That re-reads only the documents already there (`engine.py:3430`).
   - A forgotten document means deleting the training and losing every approval.
3. **One change at the final review reopens the first review.**
   - `reviews._request` drops the `direction` approval for every target but scenarios and
     Yoodli, in either phase (`R/reviews.py:343-347`).
   - So under Balanced, one guide change at "Review the finished materials" brings back
     "Review the first drafts" for all levels, redraws the deck, and stops at its gate.
     Only then does the final review come back.
   - The hint says only "If it changes, these are written again from it: …"
     (`TA:6325-6326`). No test covers this path.
4. **Downloads from the final review have no extension.**
   - `downloadFile` sets `link.download = name` on a blob (`TA:895-916`, `:905`), so the
     page's name wins over the server's `Content-Disposition` (`R/page.py:280-302`).
   - The final review passes `item.label`, for example "the level 101 learner guide"
     (`TA:6309-6310`).
   - Other places pass the basename (`:5276-5277`, `:8212-8213`). So two levels' guides
     both arrive as `document.md`, and every index as `README.md`.
5. **A deck waiting for a picture offers the wrong action.**
   - `ASSETS_WAIT` (`R/engine.py:322`, `2151-2152`) keeps the default action `retry`.
   - So the stop's filled button is **Try again**, with "Try again re-runs this step from
     the start…" (`TA:5012-5013`). Trying again only waits again (`test_visual_05`).
   - **Add the picture** is in the deck card far below (`TA:5935-5966`). The page never
     reads `problem.waits`.
6. **Runner pages send the person to an assistant they do not have.**
   - A missing Doc: "Ask your assistant to unlink it from the training, then …"
     (`R/copies.py:63-66`).
   - `DECK_LEFT` and `DECK_AGAIN` say "make the deck in a conversation with your
     assistant" (`R/pipeline.py:98-104`). `TA:200-201` does the same.
   - `folderCard`, "Carry on with your assistant", shows on every finished runner training
     (`TA:3106-3107`).
   - Yet `T/docs/runner.md:348` says a runner training "should not also be driven from a
     conversation".
   - `NOTICES` say "Run the desk command again in your terminal…" (`TA:21-26`). A runner
     person opened "Open Training Studio".
   - `stops.unusable` says "Check this computer, on the Status screen, says what it
     needs." (`C/stops.py:156-161`), and the stop offers only Try again.
7. **The update notice gives a suite install nothing to do.**
   - `upkeep.versions` returns `'suite': 'marketing-studio'` and `offered` False
     (`R/upkeep.py:1230-1234`). Upgrade refuses with "Update this studio with the Marketing
     Studio installer." (`:797-798`).
   - The page never reads `.suite`. `updatesCard` says "Newer versions are ready for this
     computer:" and offers only Dismiss (`TA:7699-7716`).
   - Companion rows ignore `suite_managed` (`:1349`).
   - Presentation Studio has the same issue: `P/runner/upkeep.py:844-863`, `1302-1306`,
     `1424`, and `updatesCard` at `D/app.js:6485`.
8. **Smaller dead ends.**
   - With Yoodli on, the brief and the practice scenarios have no **Skip this stage**, and
     nothing says why (`T/skills/training-studio/scripts/desk.py:511-513`).
   - Missing answers say "Start a new training in its place." with no action
     (`R/pipeline.py:1278-1279`).
   - "A scenario of your own" is described (`TA:208-211`, `T/docs/runner.md:231`), but the
     runner has no way to give one.
   - The question limits, 8 lines of 300 characters (`pipeline.py:476-477`), are checked
     only after **Start the training**.
   - Bring-in refuses a folder that is itself a Git repository (`R/team.py:356-358`).
   - A brought-in conversation training whose documents-scoped plan has not started may
     wait for documents again (`R/engine.py:5034-5035`). The audit did not verify this end
     to end.
   - Stop loses the step's work, and it has no confirmation (`TA:4956-4957`).

### Blog Studio

1. **A teammate cannot take over a desk blog.**
   - Every desk write runs `team_workspace.guard` (`B/scripts/team_workspace.py:60-65`).
     It raises "…It can be read here. Take it over to change it."
     (`B/scripts/studio_sync/team.py:172-175`).
   - The desk has no Take control (`M/desk.js:310-319`). `sRun` returns before its team
     buttons for a desk blog (`M/runner.js:253-254`).
   - The server fails too. `team_workspace.action` checks `expected` against
     `blog_runner.survey` (`:402-408`). `load` raises "This blog has no guided run. Choose
     Run this blog on the page." (`B/scripts/blog_runner.py:564`).
   - `desk_jobs.view` returns no driver (`B/scripts/desk_jobs.py:1649-1717`).
2. **A stopped desk start can only Retry.**
   - "This start stopped before the draft was ready. Retry the step when you are ready."
     (`M/desk.js:278`).
   - Retry runs the same step again (`desk_jobs.py:1186`).
   - The failure kind is lost: `tool_jobs.py:282` keeps only `error`, and
     `WorkerFailure.reason` and `.said` (`blog_worker.py:37-44`) are dropped.
   - So none of Phase 1's ways on are offered: **Try again with more time**, **Continue
     without research**, **Open Status** and "What the assistant said" (`M/runner.js:85-90`,
     `254`).
3. **Restoring a deleted desk blog dead-ends.**
   - Restore says "Restored … It stays stopped until you resume it." and opens the run
     screen (`M/runner.js:1069`).
   - The run read raises the `:564` message, so the page shows "This view could not be
     read" (`runner.js:119`).
4. **A desk blog can never get a Google Doc.**
   - The toolbar has "Google Doc ↗" only for a Doc already linked (`M/desk.js:314`).
   - "This blog has no Google Doc to send to…" (`:874`).
   - `google-open` guards a run (`B/scripts/management.py:1926-1934`).
     `google_handoff.open_as_doc` calls `blog_runner.load` and requires a complete run
     (`B/scripts/google_handoff.py:37-49`).
   - `B/references/page-tools.md:49` says "Open as a Google Doc: on Done".
   - A Google Doc already linked to an older run refuses on the desk start with "This
     blog has a step-by-step run. Open it there." (`B/scripts/desk.py:313`), and offers
     no way there.
5. **The Proofread panel describes Apply a voice.**
   - `sDeskProofView` uses `DESK_TOOLS[1][2]` (`M/desk.js:813`). Index 1 is `voice`
     (`:597-605`).
6. **Desk blogs never reach the team library.**
   - Only an older run's Finish calls `keep_finished` (`blog_runner.py:1761-1763`, `1818`).
   - **Mark as published** (`M/desk.js:517-521`, `management.py:2005-2016`) keeps nothing.
   - The library lede "Finished blogs, files, links and Google Docs your team writes
     from…" (`M/app.js:48`) is no longer true for new posts.
7. **The library upload starts a blog off the desk.**
   - "Start an editable blog from this file" (`M/index.html:43`, `M/app.js:646`) makes a
     manuscript-editor blog (`management.py:943-961`).
   - This contradicts "Every new blog starts on the writing desk"
     (`docs/design/blog-workflows.md:23`).
8. **A long paste is refused only after Start.**
   - The field allows 1,000,000 characters (`M/desk.js:175`). The server takes 200,000:
     "Use a draft up to 200,000 characters." (`desk.py:18`, `:328`).
9. **The start hides what step 3 decides.**
   - Step 2 shows research and Length from `have` (`M/desk.js:87-88`), but `have` is
     chosen in step 3.
   - So ticked research is dropped with one line, "A draft you bring is edited as it is,
     without research." (`:186`). Switching to a topic never offers Length.

### Marketing Studio home and setup

1. **One setup step has three titles.**
   - Step 1 shows "Step 1 of 3" (`C/setup_web/app.js:94`), the progress item "You and
     your assistant" (`index.html:44`), the large title from `labels[step]` (`app.js:92`)
     and the card title "You and your assistant" (`index.html:46`).
   - Step 2's progress item and large title say "Your workspace", and its card says
     "Where your work lives" (`index.html:69`).
2. **Shared settings has two saves.**
   - "Save settings" ends the form (`index.html:109`). Then **Studio installations**
     follows with its own "Save installation folders" (`:111`, `app.js:498-502`).
3. **The shared page asks Blog-only people about stops that never happen.**
   - "When should work stop for your review?" with "New work saves this choice"
     (`index.html:65-66`). Blog Studio's own first run asks it too.
   - So does "Deliver as" and "Slide previews" (`:94-97`), which only the deck studios
     read.
   - "You can change it for each blog, presentation, or training." (`:79`) is false for a
     desk blog.
   - "After each decision" (`:75`) is a stop's word. The desk shares after a rewrite or an
     applied change.
   - Blog Studio's card says "Shape your ideas into blogs in your voice."
     (`marketing_studio/catalog.py:6`), but voices are off by default.

### Copy that says what the page does not do, and many names for one thing

- **Presentation Studio, true only at Step by step:**
  - "you confirm whether it is a finished script…" (`D/app.js:116-118`, `2838-2840`).
  - "You approve the research plan, then the findings, before the outline is drafted."
    (`:3129-3132`).
  - "From the first decision on, you see the slides themselves." (`:3185-3186`).
  - "…and stops each time it needs your decision." (`:1437-1439`).
  - "Your decision" on every gate, even "Continue the outline automatically"
    (`:3700`; `engine.py:2757-2760`).
  - Under Balanced, the beads say **Look** is "Still to come" while its samples are on
    screen (`stagesOf`, `:3644-3658`).
- **Presentation Studio, names and voice:**
  - Three "revision" counters (`deliver.py:16-17`, `team.py:306-308`, `D/app.js:4849`).
  - "Deliver to Google Slides" against the **Send to Google Slides** button.
  - Assistant, agent, worker and AI (`:2555-2557`, `:3839`).
  - "We" and "us" (`:129-130`, `:3982`, `:5028`, `stages.py:30`).
  - Successes in the red alert (`:1574`, `:4861`).
  - "searched on the web" for any plan (`:4039-4040`).
  - A warning bead on normal progress (`:4828`).
  - "Ask about this finding" reruns all the research. Its aria-label still says "Don’t
    research it again" (`:4239-4248`).
  - Asking for a change has about a dozen names.
- **Training Studio:**
  - The review level card contradicts itself. `REVIEW_SAYS.automatic`, "Stops only for
    the finished materials.", sits under "it stops for each drawn deck" (`TA:171-177`,
    `4668-4676`).
  - "Review the first drafts comes after research and the blueprint, guide and brief for
    each level" is wrong for layout 2 (`TA:4683-4685`).
  - The run over-counts a documents-only Balanced training's stops by one
    (`R/engine.py:1049-1055`).
  - "A deck of this size has cost about $X … before." is a fixed rate, not history
    (`TA:5893-5900`).
  - "Approving finishes this draft" is said of a whole training (`TA:6060`, `6244`).
  - A lower-case sentence start (`R/copies.py:183`).
  - The web-only refusal also speaks for sites-only research (`engine.py:3791-3792`).
  - The team sentence in `DELETE_SAYS` shows for a local workspace too (`TA:305-306`).
  - There are two or more names for the research plan, blueprint, guide, brief, practice
    scenarios, Yoodli scenarios, the index, leaving the deck out, both reviews and the
    deck outline (training findings, part B, section 2).
- **Blog Studio:**
  - "Desk" still names the whole page in server and old-page messages
    (`management.py:2339`, `2358`, `2305`; `M/app.js:126`, `161`, `384`; `desk.py:1184`).
  - "Tighten and proofread" (`M/desk.js:5`) is an assistant job. Finishing's Proofread is
    not.
  - The Default voice hint (`runner.js:200`) is false for desk blogs.
  - "Your documents are always read." sits beside a tick (`runner.js:65`).
  - The Where new work stops toast says "New work in every studio…"
    (`runner.js:72`).
  - Kind of post and style; voice guide, voice and voice profile (`runner.js:653-796`,
    `919`, `742`).
  - The All blogs details speak the old flow for desk blogs (`management.py:1137-1245`).
  - The interview names the wrong place to resume (`runner.js:969`).
  - Status says "Every run" (`runner.js:186`).
  - Home says "Review <title>" for a stopped start (`runner.js:181`).
  - The Sources panel says "No sources were given for this draft." when research ran
    (`desk.js:407`).

## Design

### Presentation Studio

**1. A combined stop is hosted where the run has a stop.** `deck_flow.stops` takes the
run's gate names. When a level's host gate is not among them, the combined stop falls to
the gate of its last folded checkpoint that the run does have. Under Balanced, a Redesign
deck's `gate:look` is then a stop. `review_policy.automatic` and `review_policy.ahead` pass
the gate names through. Training Studio's host, `review:direction`, always exists, so
Training is unchanged. The default-look receipt names what happened.
`DEFAULT_WORDS`, which Training Studio also uses, stays the Automatic draft sentence.
Presentation's `choose_default` takes the level, and uses a new `deck_flow.DEFAULT_KEPT`
at any other level: "The brand's default look, {name}, was used: no look was picked in
the direction review." `look.approve` writes "In their words" only for a look the person
picked; a receipt by the review policy is written as "Recorded: …". `stopsFor` on the form keeps `gate:look` under
Balanced when the route has no `gate:outline`.

**2. Every route is walked at every review level.** One table,
`P/tests/route_stops.py`, says which gates stop for each route and level, at each review
level. The route walks and a new form test both read it, so the walk and the form's
"where it stops" line cannot drift apart. Gates the level passes must carry a
`by: 'review-policy'` receipt.

**3. A delivered PowerPoint file is shared.** On a PowerPoint delivery, `deliver.upload`
copies `work/deck.pptx` to `deck.pptx` in the deck's folder and records
`pptx: 'deck.pptx'`. That file is committed and shared like `deliver.json`, and a new
delivery replaces it. Download serves the shared file when it is there, so a teammate's
screen has **Download .pptx**. **Send to Google Slides** uploads the shared file when
`work/` has none. An older delivery that recorded `work/deck.pptx` keeps it. On another
computer it says "This delivery's PowerPoint file is on the computer that made it. Deliver
it again there to share it." Home's line becomes "A .pptx on the computer that made it."
for those deliveries.

**4. Undo only when it can be done.** `gitstate.can_undo(workspace, path)` checks
`undo`'s conditions without changing anything. The view carries `undo: bool`, and the page
shows "Undo the last step" only when it is true.

**5. "That’s wrong" says its price first.** It opens a sheet titled "Read it as <other
kind>?". The sheet shows what is drawn again and what it last cost, with **Read it again**
and **Cancel**. The price comes from `Engine._reclassify_price`: `_redo(record,
'gate:classify')`. When the new reading is material and research is on, it adds "The
research runs first, for the first time; this computer has no record of what it costs."
The classify stop's own chip at `D/app.js:4022` is unchanged, because nothing has been
drawn by then.

**6. Status says whether Google is signed in.** `computer.py` in each deck studio's
`skills/<studio>/scripts/` adds a Google item. It runs `gcloud auth list
--filter=status:ACTIVE --format=value(account)`, which works on this computer only and
never uses the network. It says "Signed in as <account>." or "Not signed in. In a
terminal, run `gcloud auth login --enable-gdrive-access`, then check this computer
again." The page's lines name that item and the real button:
- "Google is not connected on this computer, so approving makes a PowerPoint file. Sign
  in to Google (Status → Check this computer says how), then choose Send to Google
  Slides."
- "Sign in to Google (Status → Check this computer says how) to send this deck to Google
  Slides later."
- `existing.NOT_READY`: "Sign in to Google first: Status → Check this computer says how.
  Or download the file and upload it."

**7. Questions can be added at the research stop.** The synthesis branch of
`researchPanel` adds `addedPart(gate)`. Together with the plan's questions it is capped at
`PLAN_MOST` (8), which the view sends as `gate.most`. The sheet's price line is
`research_price`, because an added question runs the investigation again.

**8. Copy true at every level, and one name per thing.** The form's lines come from the
same stops the runner makes. The route card says "It is read first, to tell a finished
script from material to build from." The research chip, the start line and Home's line are
said by level, from `stopsFor`. "Your decision" is only on gates that stop. Under Balanced,
the beads place "Review the direction" under the stage it is in. See the names table below.

### Training Studio

**1. A teammate's Google Doc edits come back.** The copies card gains **Look for changes
in Google Docs**. It is a request from the person, so the network is used only when they
ask. `copies.check(root, transport)` runs `gdocs.status` for each linked copy and records
`remote changed` or `both changed` in `record['copies']['remote']`. A remote change on an
unchanged file shows "Changed in Google Docs" and **Bring the Doc's changes in**, which
pulls cleanly. A both-changed copy shows today's choice. The button condition reads
`found.remote` and no longer matches a problem string. `copies.pull` returns `unplaced`.
The page then says: "These headings were brought in but not placed in the guide's
sections, because their hidden note was removed in the Doc: <headings>. Put them back
under a heading, or ask for changes."

**2. A document after research is planned, and a priced research update.** For a
training whose `research_from` reads documents, `Engine.supply('add')` no longer refuses
once the plan is settled, as long as the training is not working. The document is kept in
`sources/supplied/` and listed in `record['documents']['later']`, and nothing is
researched. The documents card says "Added after the research: not read yet." and offers
**Update the research**. Its sheet is priced with `research_view.price`. It names what is
made again from the research, using `reviews.rewritten(root, session, decks,
'research')`. Confirming records a
research request `{'refresh': True, 'added': [names]}`, which reopens research as
**Bring the evidence up to date** does. A document added later can be removed until the
update runs. A web-only or sites-only training refuses with "This training's research
does not read documents, so it takes none. Start a new training that reads your
documents to use this one." Two matrix rows.

**3. A final-review change stays in the final review.** `reviews._request` drops the
`direction` approval only when the request is made in the direction phase. A deck outline
rewritten by a final-review change is accepted by the policy with a receipt. The drawn
deck still stops at its own gate, as every drawn deck does. The hint says: "If it changes,
these are written again from it: …. They come back to this review." When a deck is among
them, it adds "The deck is drawn again and stops for you first." The matrix row is updated.

**4. Downloads keep the server's name.** `downloadFile` takes the file name from the
response's `Content-Disposition` (`filename="…"`). It falls back to the name it was
passed only when there is no header. The toast names the saved file. Every caller keeps
passing a fallback with an extension.

**5. A picture wait leads with the picture.** `ASSETS_WAIT` uses the action `asset`,
labelled **Add the picture**, which opens the deck card's picture form and focuses its
file field. `actionSays` for `waits === 'assets'` says "The deck is drawn once its
pictures are here. Without one, redesign the deck or leave it out." Drawing without a
picture changes the approved design, so it goes to piece 6.

**6. Runner pages never send the person to an assistant.**
- A missing Doc offers **Make a new Google Doc**, which unlinks the copy and makes it
  again. The missing-Doc sentence in `copies.REWORDED` says "Google could not find the
  Doc. It may have been deleted, or the signed-in account cannot open it. Make a new
  Google Doc from here."
- On a runner training, `DECK_LEFT` and `DECK_AGAIN` say "Put that right and check this
  computer again, or leave the deck out." The page's `DECK_LEFT` follows them.
- `folderCard` shows only for a training with no `run`.
- `NOTICES` say "Open Training Studio again and use the new link." under the runner, and
  keep today's words for `training desk`.
- `stops.unusable` gets an **Open Status** action in both deck studios, as Blog Studio
  has.
- Missing answers offer **New training** and **Delete this training**.
- `WHOSE.you` and `T/docs/runner.md:231` say that a scenario of your own comes only from
  a conversation training.

**7. Smaller dead ends.**
- With Yoodli on, the gate's menu shows "The brief and the practice scenarios cannot be
  skipped while Make scenarios for Yoodli is on: Yoodli uses both."
- The research-questions field checks 8 lines of up to 300 characters as the person
  types, and **Continue** refuses with the same sentence the runner uses.
- Bring-in leaves out the folder's own top-level `.git` when it copies, and still refuses
  a repository nested deeper. The sheet says "Its own Git history stays where it is."
- The brought-in documents case is tested first. If the test passes, the finding was
  wrong and nothing changes. If it fails, a brought-in training whose `sources/` holds
  documents is marked done with them.
- **Stop** opens a sheet that says the step's work is lost and that Pause lets it finish.

**8. Copy and one name per thing.**
- `REVIEW_SAYS` becomes `reviewSays(level, planned, deck)`, from the same rule as the
  Ready card.
- The briefs line says "Review the first drafts comes after research, the blueprint and
  the learner guide of each level. Briefs are written after it."
- `Engine` counts the stops with `pipeline.plan_from_form(record)`, so a documents-only
  Balanced training says one fewer.
- The deck cost says "is estimated at about $X (a fixed estimate per slide, not this
  computer's history)".
- "Approving finishes this training."
- A sentence never starts lower-case: `copies.BOTH` capitalises its label.
- See the names table below.

### Shared: the suite update notice

When `versions()` returns `suite: 'marketing-studio'`, both deck studios' Updates card and
Status → Versions say: "Marketing Studio installs and updates this studio. To update it,
unpack a newer Marketing Studio release and run `marketing-studio update --from <the
unpacked folder> --yes`." They offer no Update button. `upkeep` sets companion rows'
`update.offered` False when suite-managed, so nothing offers an update that would be
refused. Blog Studio has no self-update, so nothing changes there.

### Blog Studio

**1. A teammate can take over a desk blog.** `desk_jobs.view` returns `team` and `driver`
the way `blog_runner.describe` does for a run. `team_workspace.action` reads `expected`
from `desk_jobs.view` for a blog on the desk (`desk.on_desk(directory)`). The desk toolbar shows "<name>
· driving on another computer" with **Take over**, and "Nobody is running this blog" with
**Take this blog**. While the blog is ours it shows **Hand over**. Each opens the existing
`sTeamDecision` sheet. While someone else drives, the desk is read-only, with the sentence
from `team.elsewhere`.

**2. A stopped desk start has Phase 1's ways on.** `tool_jobs` keeps a failed job's
`reason` (`cli`, `time-limit` or `research`) and `said`. `desk_jobs.stalled` returns them
with the step. The progress screen offers:
- **Try again with more time** for `time-limit`, with `sTimeWords`; `desk-retry` takes
  `seconds`.
- **Continue without research** when the research step stopped; `desk-retry` takes
  `skip_research`, which drops the step and records no research.
- **Open Status** and "What the assistant said" for `cli`, with `sCliFailure`.
- **Retry** always.
- **Delete this start** ends it without the lists.

**3. A restored desk blog opens on the desk.** `blog_delete.restore` returns `on_desk`,
and the page routes to the desk with "Restored <title>." The run route answers
`{'on_desk': True}` for a blog on the desk instead of raising, so no address dead-ends.
`blog_runner.load`'s message becomes "This blog has no step-by-step run. Open it from
Blogs."

**4. A desk blog can get a Google Doc.** A new desk route, `desk-google-open` (confirmed,
expected), calls `google_handoff.open_as_doc(..., desk=True)`. That reads the item and
`DRAFT.md` without `blog_runner.load` and with no complete-run check. It then links the Doc
and its baseline the way the Done card does. The toolbar shows **Make a Google Doc** when
none is linked. Its sheet says "A private Google Doc of this draft is made in your Drive.
Later desk changes are sent to it as suggestions." The Before publishing card then sends
suggestions to it. On the desk start, a Doc linked to an older run offers **Open its run**.

**5. Proofread describes Proofread.** `DESK_TOOLS` becomes keyed by name (`deskTool('proofread')`),
and no index is used.

**6. Mark as published keeps the blog in the team library.** The `schedule` route with
`desk=True` and stage `published` calls `blog_library.keep_written`, as `keep_finished`
does. A library failure never refuses the publish. The sheet adds "Its draft is kept in the
team library as a reference and an example of its kind of post. Marking it again updates
that item."

**7. Library upload opens the desk start.** The tick reads "Then edit it on the desk". After
the upload saves, the page opens the desk start at "What do you have?" with **A draft**
and the file's text in place. The upload no longer sends `as_blog`.

**8. The paste field takes what the server takes.** `max: 200000`, with the hint "Up to
200,000 characters. Each ## heading starts a section."

**9. The start asks what you have first.** `DESK_START_STEPS` becomes 1 What are you
writing? 2 What do you have? 3 Sources and settings. Step 3 shows research and Length
for the `have` chosen. This order is for a topic or an outline: a draft to polish or
review is already one screen with no kind of post (only Reshape asks for one), and A draft
switches to it.

**10. Copy and names.** See the names table. The server and old-page messages say "Blog
Studio's page" or "this page" where they say "desk". The first pass is **Tighten and
correct**. The Default voice hint says "Used for Interview me and for blogs written step by
step in chat. A blog on the writing desk is written with its tone." The documents line is a
sentence, not a tick: "Your documents are always read. Choose what else research may
use." The Where new work stops toast says "New decks, trainings and blogs run step by step
in chat now start at <level>." The Sources panel says "Research was read for this draft."
with the research's source count when research ran. The All blogs details for a desk blog
say "On the desk" and **Open on the desk**, and drop the requested stop and Continue in
chat lines. The interview says "Pause by closing; resume it from Blogs, with Resume
interview." Status says "Every blog". Home's filled button for a stopped start says
"Open <title>".

### Marketing Studio home and setup

**1. One title per setup step.** In setup, the numbered progress list ("1. You and your
assistant", "2. Your workspace", "3. Brand and delivery", the current one marked) names
the step. The large title and "Step n of 3" are not shown, and each step's card title is
the step's name. Shared settings, outside setup, keeps its large title.

**2. One save.** The Studio installations fields move into the settings form, as its last
card, outside setup. **Save settings** sends the shared changes, then the folders when
they changed. If the folders fail after the shared settings saved, it says "Your shared
settings were saved. The installation folders were not: <reason>."

**3. Shared copy that holds for every studio.**
- The review-level hint adds "A blog on the writing desk has no stops: this sets where
  new decks, trainings and blogs run step by step in chat stop."
- The sub-heading becomes "Where new work stops", the one name for the setting.
- "Share changes" offers "After each decision or applied change" and "When I ask".
- The brand line says "You can change it for each presentation or training. Blogs written
  step by step in chat use it too."
- The models hint adds "Blog Studio uses Main for every job."
- Blog Studio's card says "Write blogs on one desk, from a topic, notes or a draft."
- In Blog Studio's own first run (`product === 'Blog Studio'`), the review-level part and
  "Delivery and previews" are hidden, and their saved values are left as they are.

### One name per thing (extends Phase 2's table)

Stored values do not change. Only what a person reads does.

| Studio | Thing | One name | Replaces |
| --- | --- | --- | --- |
| All | The setting | Where new work stops | Review level, When should work stop for your review? |
| All | The AI that drafts | assistant | agent, worker, AI ("A worker asks:" becomes "The assistant drawing <section> asks:") |
| All | Where work is kept | workspace | work folder, where your decks are kept |
| Presentation | Delivering to Google | Send to Google Slides | Deliver to Google Slides, deliver it again |
| Presentation | A delivery's number | Revision n (deliveries only) | "Published as revision n" becomes "Published on <date> (revision n)"; "this displayed revision" becomes "the slides shown here" |
| Presentation | The critic's pass | the check | the review ("The review has nothing left to raise" becomes "The check has nothing left to raise") |
| Presentation | The brand's pass | the brand check | Audit blocker, brand audit |
| Presentation | A change to something made | Ask for changes (… to this slide, … to the research, … to this finding) | Send slide feedback, Request changes to the research, Ask about this finding |
| Presentation | Leaving a finding as it is | Keep it as it is | Keep this finding, Don’t research it again |
| Presentation | Voice | "you" and "your" | we, us ("What you gave us" becomes "What you gave") |
| Training | Research plan | research plan (bead "Research plan") | Questions, research questions |
| Training | Blueprint | blueprint | teaching plan, teaching blueprint |
| Training | Guide | learner guide (bead "Guide") | document, The document |
| Training | Brief | reference brief, of a product or of competitors | knowledge brief |
| Training | Practice | practice scenarios (bead "Practice") | scenario |
| Training | Yoodli output | Yoodli scenarios ("Write the Yoodli scenarios") | Yoodli field layouts, layouts, fields, handoff, Build the Yoodli scenarios |
| Training | Last stage | the index (bead "Index") | Wrap-up, package |
| Training | Not ready | Not ready to use yet | Finished, but not ready to use |
| Training | No deck | Leave the deck out | Skip the deck for now |
| Training | First review | Review the first drafts / the first drafts review | the direction, teaching plan review |
| Training | Final review | Review the finished materials / the finished materials review | final review, finished-materials review |
| Training | The deck's words | the deck outline | what the deck says, Deck direction, the direction, the words |
| Training | Run elsewhere | Run by <name> / Run by your teammates | Run from another computer |
| Training | Walkthrough | "Choose this to see how each slide is drawn, and approve the design in one decision." | "…one at a time." |
| Training | Default look, in a review | Use the brand's default look (a choice) | Carry on in the brand's default look (that stays the run's action) |
| Blog | Kind of post | kind of post ("New kind of post", "Write the guide by hand", "Edit this guide", "Export this guide", "Name", "Learn this kind of post", "Learn a kind of post from these", "All voices and kinds of post") | style, style guide |
| Blog | Style sample role | "Style sample: to learn a new kind of post from" | "Example of a kind of writing (style sample)" |
| Blog | Voice profile | voice guide ("Name", "Retire this voice guide") | voice profile, Profile name, Retire this profile |
| Blog | Tools on old runs | History, Headline and opening, Feedback without a rewrite, Check facts against sources | Saved manuscript revisions, Improve a title or opening, Review argument and structure, Check facts |
| Blog | First pass | Tighten and correct | Tighten and proofread |

## Moved to other pieces (a redesign, not a fix)

- Presentation: reading a published revision as it was published, swapping the original
  of an existing deck, and Recently deleted with Restore. These are features. They are
  built once the runner is shared (piece 2), as part of pieces 5 and 6, whose History and
  Restore they extend.
- Training: reading a published revision (piece 6), "draw it without this picture" (piece
  6), a slide-level deck fix (piece 6), and widening where a training's research looks
  (piece 6's Sources panel).
- Blog: research, spend and grouped objections on the desk; who drives in the lists;
  changing kind of post and tone after Start; Tools against Finishing (piece 3, the shared
  desk); brand and author for desk blogs (a decision for piece 7).
- Settings with three ways into one value, two brand settings, and the Shared settings
  button that leaves the studio in the same tab (piece 4).

## Out of scope

- Deleting code, routes, CSS and stale docs, and the shared runner (piece 2). Piece 1 stops
  calling the library upload's `as_blog` branch; piece 2 deletes it.
- Layout rules on any screen (piece 4).
- The desks (pieces 3, 5 and 6).
- Removing review levels or their controls (piece 7).

## Testing

Disposable settings (`STUDIOS_CONFIG`, `HOME`, `PRESENTATION_STUDIO_DATA`), workspaces, Git
identities and processes. Scripted workers, stand-in Harness Slides, fake gcloud and Drive
transports. No provider job, no Google call and no assistant job.

- **Core:** `deck_flow.stops` with and without the host gate; `review_policy.automatic` and
  `ahead` agree for every product, level and gate set; `stops.unusable` carries its action.
- **Presentation:** every route at every review level from one table, the walk and the
  form; delivery shared and downloaded on a second clone; undo offered only when it can be
  done; the reclassify price; the Google item on Status; added questions at the synthesis
  stop; copy assertions for each new and removed string.
- **Training:** matrix rows and `test_row_NNN` tests for the Doc check, a document added
  later, the research update and the final-review change; download names; the picture
  stop; runner copy with no assistant; the suite card.
- **Blog:** take over, stopped-start exits, restore, desk Google Doc, the library keep,
  Proofread text, paste limit, the upload, start order. Python tests and
  `check-management.cjs` journeys.
- **Marketing Studio:** setup titles and one save, under node with `tests/settings_page_harness.js`.
- Each studio's full suite, the root suite and `tests.test_ui_consistency` once before the
  pull request.
