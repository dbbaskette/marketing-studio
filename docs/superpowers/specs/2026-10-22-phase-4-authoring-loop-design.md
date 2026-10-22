# Phase 4, finish the authoring loop on the page: design

**Date:** 2026-10-22, at main 21a216e. **Owner's words:** "write the spec for phase 2,3,4,5.
Then write the implementation plan for each."

Phase 4 of `2026-10-21-authoring-workflow-review.md`. Phases 1 to 3 make research finish,
make the page's words true and make the research stop worth it. This phase closes the loop
so that a piece can be finished without leaving the page: what was made can be taken away,
what a teammate changed can be brought back, a review's findings can be applied, and a
review cannot be approved on something nobody saw.

Phase 4 starts after Phases 2 and 3 are merged. Where Phase 2 renames a thing (the first
combined review, the look stop, the handoff), this document names it by its code: the step
`review:direction` in Training's `runner/reviews.py`, the gate `gate:look` in Presentation,
the stage `package` in Blog Studio. The labels on the page are whatever Phase 2 left.

## What is wrong now

### Training Studio

- **Nothing made can be taken away from the page.** A deck's gate says "This is not text,
  so it is not shown here. It is 2.3 MB. Open it from the training folder:" and a path to
  copy (`desk/app.js:2040-2046`). A Word copy says "Kept with the training as" and a path
  (`app.js:5189-5194`). The page server has no route that answers a file's bytes
  (`runner/page.py:174-180`); Presentation Studio has one (`/api/download`,
  `presentation/runner/page.py:241-246`) and the fetch-then-save pattern on its page
  (`presentation/.../desk/app.js:4722-4740`).
- **A teammate's edit in a Google Doc blocks the copy for good.** `copies.py:60-62` tells the
  person "Someone has changed the Google Doc since it was last sent, so it was left as it
  is. Ask your assistant to bring those changes into the training, then try the copies
  again." The page has no way to do that, although `gdocs.pull` exists
  (`scripts/gdocs.py:302-344`) and the page's own rule is that the runner, not a
  conversation, decides a training it drives.
- **Balanced's first combined review writes too much before it stops.** `reviews.group`
  (`runner/reviews.py:57-68`) puts every level's guide and brief before `review:direction`,
  and `reviews.commits` (`reviews.py:130-142`) lists every wanted material as what approving
  will write, including the guides the person has just read. The deck's outline reads the
  guide (`pipeline.py:1741-1756`), so the guide must stay before the stop. Nothing reads a
  brief before the deck is built except the Yoodli scenario, which is built after.
- **"Finish this level, then wait" pauses where nothing can be decided.** Under Balanced and
  Automatic the run prepares every level before its first combined review. `_controls`
  (`engine.py:4237-4252`) offers the control while a level's guide is being written, so the
  run halts after one level's preparation, before a review that needs all of them.
- **The combined reviews have no bead.** `desk.stage_row` (`scripts/desk.py:209-240`) makes
  one bead per stage; `review:direction` and `review:final` are steps of stage `review`,
  which has no bead, so the row shows nothing where the run waits longest.
- **Approve's "what happens next" lasts four seconds.** After a decision the page toasts
  "Approved. " and the run's sentence (`app.js:5778`), and the run screen then shows only
  the working line.
- **Yoodli's copy buttons live only on a gate Balanced skips.** `yoodliCopies`
  (`app.js:2135-2146`) is drawn only on a single Yoodli scenario's gate (`app.js:2440`);
  under Balanced and Automatic those scenarios are read inside the final combined review
  (`app.js:5825-5900`), which has no copy buttons.

### Blog Studio

- **Three start choices are not on Home.** `BLOG_MODES` has `outline`, `revise` and `review`
  (`assets/management/runner.js:5`) and the start form handles them
  (`runner.js:173`, `blog_runner.py:980-1001`); the start tasks list five other cards and
  not these (`runner.js:311`).
- **The Done card dead-ends.** It offers Copy Markdown, Download and "Polish or edit the
  draft" (`runner.js:846-860`). Pre-publish and Repurpose are in Tools (`runner.js:503-507`).
  A blog with no linked Google Doc cannot be opened as one from the page: the first handoff
  is chat-only (`references/short-commands.md:35-39`), and `google_drive.Client.import_new`
  refuses Markdown (`scripts/google_drive.py:516-520`).
- **Nothing applies the review's findings.** Fixing them means "Ask for changes → Draft"
  and writing the request by hand.
- **The review aside is folded and says little.** It sits in a closed
  "Review notes and checks" disclosure (`runner.js:254`). "Checked for you" has two rows
  that are always true (`blog_runner.py:2349-2357`): readable text, and "matches its
  submitted version". The voice-rule findings the worker gets (`text_checks.lint`,
  `blog_runner.py:1619-1624`) never reach the person. The preservation check is appended to
  the notes as raw JSON (`blog_runner.py:1257-1260`), so "Worth a look" shows
  `Preservation check: {"needs_review": …}`.
- **Explore ideas ends at an unreviewed draft.** `develop` sets the pipeline to
  `['outline', 'draft']` (`blog_runner.py:2411-2420`); every other path ends with review
  and package.
- **"Keep in the team library" depends on order.** The tick applies to files added next
  (`runner.js:984-986`); a file added before or after the wrong tick cannot be moved by its
  row.

### Presentation Studio

- **Balanced's direction review can be approved with no look picked, then refused.** The
  approve composition sends `look` only when one is held (`desk/app.js:4944-4948`); the
  server refuses with `NO_LOOK` (`runner/engine.py:2114-2128`), two screens above the picker.
- **Editing the outline after picking a look applies the pick to looks nobody saw.**
  `_look_policy` (`engine.py:2131-2146`) applies `record['look_picked']` by id to whatever
  looks are shown; when the outline changed, `look.choose` drops the samples and they are
  drawn again (`steps/look.py:212-245`), and the next pass applies the old pick to the new
  drawings without a stop.
- **The scratch route has nowhere to write a brief.** The route card says "Say what it is
  about and who it is for" (`app.js:115`). `notes` is read by the outline job
  (`steps/outline.py:365-367`) and the research plan (`research_steps.py:267`) and has a
  limit (`decks.py:34`), but `check_form` drops it (`decks.py:126-128`) and the page never
  sends it (`app.js:3041-3047`).
- **Your own delivered deck needs "Take it" before you can change it.** Delivery sets
  `record['driver'] = None` (`engine.py:1504`); in a team workspace the page then reads the
  deck as nobody's and asks the person who just delivered it to take it
  (`app.js:5439-5444`).
- **A deck delivered as PowerPoint by choice can never go to Google Slides.**
  `deliver_again` sends only a deck that fell back because Google was not connected
  (`engine.py:3127-3130`).

## Design

### Training Studio

#### T1. Download every deliverable

`GET /api/download?path=<training>&artifact=<name>[&copy=word]` answers a managed file's
bytes as an attachment. It is a read (`READS`), so it keeps every rule the page has: local
host only, the key in its header, nothing for a training this computer does not know.

- `artifact` is one of the training's artifacts (`desk.artifact_of` refuses others with
  403) or `README.md`, the index. The file is `workspace.artifact(...)['file']`, or for
  `copy=word` the Word copy the record lists (`session['exports'][name]['file']`). Every
  path goes through `desk.inside`, so a symlink or `..` that leads out is 403.
- A file that is not there yet is 404: "<file> has not been made yet."
- The type is from the suffix: `.pptx`, `.docx`, `.pdf`, `.md` (`text/markdown;
  charset=utf-8`), `.json`, else `application/octet-stream`. The name is
  `<training folder>-<level>-<file name>`, with anything but letters, digits, `.`, `-` and
  `_` made `-`. `Content-Disposition: attachment` so a browser never renders it in the
  page's origin.
- The page fetches with the key, as Presentation Studio does, and saves through a blob.
  **Download** appears on the gate of a file that is not text (beside "Copy where it is"),
  on each row of Made so far, on each Word copy, on the index screen, and on every material
  in the final combined review. A Google Doc copy keeps "Open the Google Doc".

#### T2. Pull the Google Doc

The copies card gains, on a Google Doc copy whose problem is that the Doc changed, **Bring
the Doc's changes in**. `POST /api/copies` with `{"path", "pull": "<artifact>"}` runs
`copies.pull`, which wraps `gdocs.pull` with the copies' transport:

- Only the Doc changed: the Doc's text replaces the file as an edit (`workspace.save(...,
  edit=True)`). The file is then not approved; the run comes back to its gate, and what
  is built from it is out of date and is built again after approval, as for any edit.
  The toast says "The Doc's changes are in. Review <label> again; what is built from it
  is made again after you approve."
- Both changed: nothing is overwritten. `gdocs.pull` keeps the Doc's text beside the file
  (`<file>.remote.md`). The card then offers **Use the Doc's version** (the remote text
  saved as the edit, as above) and **Keep this version and send it** (push with `force`),
  each behind a confirmation that names what is replaced. The words come from
  `copies.REWORDED`, without "Ask your assistant".
- The pull is refused, with 409, while a worker is building that file or anything from it.

Matrix rows 119 and 120 record the two transitions.

#### T3. A cheaper first combined review

For runs started after this change (`run['review_layout'] = 2`), `reviews.group` keeps the
blueprint and the guide of every level, and the deck's handoff, brand, outline and look,
before `review:direction`, and moves the brief of every level (and its copies) after it. The
guide stays before because the deck's outline is written from it; the brief has no reader
until the Yoodli scenarios, which are built after the stop.

`reviews.contents` for the direction phase leaves the brief out under layout 2, and
`reviews.commits` lists only what is still unwritten at the stop: the briefs, the practice
scenarios, the Yoodli scenarios and the decks, by their page names, plus the copies asked
for. A run with no `review_layout` keeps the old grouping and signature, so a review
already approved is not asked again (matrix row 121).

#### T4. "Finish this level, then wait" only where a level can be finished

Under a grouped review level, `_controls` gives `finish_level: None` while the next step is
one `reviews.group` puts before a combined review (`reviews.preparing(record, step)`). Once
building, it is offered as now, and the page's sentence adds "The final review waits until
every level is made." (matrix row 122).

#### T5. A bead for each combined review

`RunnerPage.with_run` passes the desk's row through `engine.review_beads(path, stages)`,
which inserts a bead `{'stage': 'review:direction', 'name': <the step's label>, ...}` after
the Brief bead (or the last bead before Deck) and one for `review:final` before Wrap-up.
Its state is `done` when the review's decision matches its signature, `review` while the
run waits there, else `not-started`. Step by step runs and legacy runs get no new bead.

#### T6. What happens after a decision stays on the screen

`engine.decide` and the combined review's approval keep `record['last_decision'] =
{'label', 'decision', 'at', 'next'}`, `next` being the run's sentence once the decision
is recorded. The run view carries it as `decided` while the run is working and has not
reached another gate, question or problem since. The run screen shows it as a status line
at the top: "You approved <label> at 10:42. <next>". The toast stays.

#### T7. Yoodli's copy buttons wherever a Yoodli scenario is read

`yoodliCopies` takes `{artifact, text}`. The final combined review draws it under each
`yoodli:` item, and the training's Done screen lists each Yoodli scenario with its copy
buttons.

### Blog Studio

#### B1. Home cards for the three missing starts

The start tasks gain **Outline only** ("Work out the argument and stop before drafting.",
mode `outline`) and **Revise or review a draft** ("Bring a manuscript; improve it keeping
the original, or get feedback without a rewrite.") which opens the start form with a choice
between `revise` and `review` and the manuscript upload the form already has. The README's
list of starts matches the cards.

#### B2. The Done card goes on

The Done card adds **Pre-publish check** (`sPrepublishTool(found.id)`) and **Repurpose**
(`sRepurposeTool(found.id)`), enabled as they are in Tools. A blog with a linked Doc shows
"Open the Google Doc ↗". A blog without one shows **Open as a Google Doc**, which:

1. refuses at once, naming Status → Check this computer, when Google is not signed in on
   this computer (`google_drive.active_account()` is None);
2. prepares a new-document transfer of the approved draft (`google_workflow` prepare with
   `new_document`);
3. imports it with `Client.import_new`, which now takes Markdown (`.md` as
   `text/markdown`), under the existing receipt, so an uncertain upload is reconciled and
   never repeated;
4. reads the new Doc back (`google_roundtrip.capture`) and confirms the transfer, so the
   Doc is the blog's linked Doc with a baseline, exactly as the chat handoff leaves it.

It is behind a confirmation: "This makes a new Google Doc of the approved draft in your
Google Drive, private to you. Nothing is shared." Sharing stays where it is.

#### B3. Apply the review's findings

At the package stop, and at the review stop when it stops, **Apply the review's findings**
(run action `apply-review`) asks for one draft job with a fixed request: apply only the
findings in `REVIEW.md`, edit only the passages they name, change nothing else. The worker
gets the findings and the preservation check is run on the result as for any draft. The
review and the package are then written again from the edited draft, because a review of
text it has not read is not a review. The confirmation says so: "This edits the draft for
the review's findings only, then reviews it and writes the handoff notes again: three
jobs." The price is Phase 2's sentence where it exists.

#### B4. The review aside, open and real

- The aside is open on every gate; the person's fold is kept for that blog while the page
  is open.
- "Checked for you" drops the two rows that are always true. It shows, for the draft,
  review and package stages: each voice rule `text_checks.lint` finds, grouped by rule with
  a count and the first line ("2 em dashes, line 14"); repeated paragraphs; passages carried
  from an example (as now); and, for a revised draft, "Numbers, links and quotations kept"
  or what changed, from `text_checks.preserve`. A stage with nothing to check says "No
  automatic checks apply to <stage>."
- The preservation check is kept on the stage as data (`run['stages']['draft']
  ['preservation']`) instead of being appended to the notes. Notes recorded before this
  change have the `Preservation check: {…}` line taken out when shown and read as the
  check.

#### B5. Explore ideas ends like every other path

`develop` sets the pipeline to `['outline', 'draft', 'review', 'package']` and the stop
point to `package`, so a developed idea is reviewed and finished, kept in the team library
and offered the Done card like any blog.

#### B6. Keep or not, file by file

Each file row on the start form says where it is ("In the team library" or "Just this
blog") and has the other as an action, until a started blog reads it (the rule
`source_role` already keeps). Moving a file into the library is a new library revision,
shared as a reference is; moving one out of it is allowed only for a file added on this
form and not yet shared. The form's tick stays and keeps applying to files added next.

### Presentation Studio

#### P1. Approve needs a look, and says so

`reviewOf` returns `blocked: 'Pick a look to approve the direction.'` when the direction
review offers looks, none is chosen and none is held, and the outline is not edited here.
The toolbar's Approve is disabled while blocked, its label stays "Approve", and the tally
reads "1 look to pick" beside the slides to change. The server's `NO_LOOK` refusal stays.

#### P2. An edited outline never takes a pick nobody saw

`record['look_picked']` gains `shown`, the SHA-256 of `work/look/shown.json` when the pick
was made. `_look_policy` applies the pick only while the looks shown are those; otherwise
it does not choose. The look gate then stops for the person, whatever the review level,
with "What the deck says changed after you picked <name>, so its looks were drawn again.
Pick again; your earlier pick is marked." and the earlier id preselected.

On the page, when the outline has been edited in the direction review, the picker says "You
edited the outline, so the looks will be drawn again from it. You pick from the new ones
before the deck is built." and P1's block does not apply.

#### P3. The scratch route's brief

The About step of the scratch route gains "What should it cover? (optional)", a long box of
up to 4000 characters: "Points, examples or a rough order. It goes to the research plan and
the outline." `formOf` sends `notes`; `check_form` keeps it with the other limits. The
document and existing-deck routes do not show it.

#### P4. Your delivered deck stays yours to change

Delivery records `record['delivered_by'] = team.computer()` beside clearing the driver,
in a workspace that has drivers. A finished deck with no driver whose `delivered_by` is this computer is read as
this computer's: no "Take it" callout, and "Ask for changes" claims it in the same request
before the change (`_take` then the decision), with one confirmation: "It runs from this
computer again, and your team sees that." A teammate's finished deck keeps "Take it".

#### P5. Send a PowerPoint deck to Google Slides later

`deliver_again` also takes a deck delivered as PowerPoint by choice: the same delivered
deck goes to Google Slides as the next revision (`delivering.upload(..., output='google')`),
and the form's choice is left as it was. The deliver card shows **Send to Google Slides**
for any delivered PowerPoint deck when Google is connected, else the sign-in sentence the
fallback already uses.

## Out of scope, and whose it is

- Wording, one vocabulary, stops and cost on every run, the "Next stop" line, three stops
  per deck, the direction review's name: Phase 2.
- What the research stop shows, triage, the source boundary, pricing research changes,
  replacing the planning job: Phase 3.
- A design stop for "redesign, keep content", live delivery by default, pictures on
  Presentation decks, `doctor`, the companions' versions: Phase 5.
- Bringing edits made in Google Slides back into a deck: neither Harness Slides nor the
  studio reads a Slides deck back into an outline today; this phase only sends.

## Testing

All tests use disposable settings, workspaces, Git identities and data folders, scripted
workers, a pretend Drive (Training's `runner_support.Drive` and `test_google.FakeTransport`,
Blog's fake `Client` in its Google tests, Presentation's `slides` stand-in), and never a
real Google call or a provider job.

- Training: the download route (every kind, refusals, traversal, headers), pull (one side,
  both sides, refused while building), the grouping under layout 2 and unchanged under
  layout 1, finish-level, review beads, `last_decision`, and page script checks for every
  new button through `page_harness.js`. Matrix rows 119 to 122 as `test_row_NNN`.
- Blog: the new cards and form choice, the Done card's actions, `open-google` end to end
  against the fake client, `apply-review`, the checks and preservation data (old notes
  too), `develop`'s pipeline, the per-file keep. Journeys in `check-management.cjs`.
- Presentation: approve blocked and unblocked, the pick bound to the shown looks, the
  scratch brief end to end to the outline's inputs, `delivered_by` and the change request
  that claims, and `deliver_again` for a deck delivered as PowerPoint by choice.
- The full relevant suites once at the end, on the shared Tart runner where possible.
