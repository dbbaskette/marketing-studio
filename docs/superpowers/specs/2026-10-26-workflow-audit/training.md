# Training Studio workflow audit (main @ cc53056, 2026-10-26)

Read-only audit.

## Early notes
- Name collision: Training Studio already calls its whole page "the desk"
  (skills/training-studio/scripts/desk.py, desk/app.js, docs/desk.md "The page",
  `training.py desk`, runner/page.py "the desk's page"). A Blog-style "training desk"
  needs a different internal name or a rename of the existing one.
- docs/runner.md:193 says a Google copy has "Bring the Doc's changes in", while
  docs/runner.md:348 says "Bringing edits back from a Google Doc ... are not in the runner yet."

---
# Sections 1–2, part A (set-up, form, documents, research, settings, status, team)
# Part A: Home, set-up, form, documents, research, Settings, Status, team, bring-in, conversation desk
(sections 1 and 2 only; app.js = studios/training/skills/training-studio/scripts/desk/app.js)

## 2. Confusing or contradictory copy (form, first batch)
- Review level card contradicts itself (app.js:4596-4616 with 4669-4677). The `then` line says "Automatic draft: it stops for each drawn deck and the finished materials"; directly beneath, REVIEW_SAYS.automatic (app.js:171-177) says "Stops only for the finished materials." Balanced's REVIEW_SAYS omits the drawn deck too, and says "Stops to read the research plan" even when documents-only skips it (startStep computes `planned`, REVIEW_SAYS does not).
- "Review the first drafts comes after research and the blueprint, guide and brief for each level" (app.js:4681-4682) is wrong for new runs: reviews.py:12-13 (layout 2) prepares only research-plan, research, blueprint, document before the direction review; briefs follow it (docs/how-it-works.md:154, docs/runner.md:196 say so).
- Stop count on the run is wrong for documents-only Balanced. engine.py:1048-1054 returns 3 + decks for Balanced ("the research plan, the direction, the finished materials"), but a documents-only plan is written from the form and accepted (docs/runner.md:372-377), so there is no plan stop. The run then says "In all, it stops and asks for your decision at least 4 times." (app.js:4966-4969). The form's own line gets this right (app.js:4665-4671).
- REVIEW_SAYS (app.js:171-177) and the form line use "the first drafts"; engine.py:304 names the same thing "first drafts review"; the run's button and README say "Review the first drafts"; the gate callout says "Request changes in the first drafts review" (app.js:2416-2418). One review, three names. The final one is "Review the finished materials" (reviews.py:109), "final review" (engine.py:304, app.js:5690 "The final review waits until every level is made."), and "the finished materials" (form).
- Invitation card (app.js:1673-1684): "Training Studio does the research and writes the blueprint, the learner guide, the brief and the practice scenarios on its own, and stops each time it needs your decision." It leaves out the deck and Yoodli. Under Balanced and Automatic draft it does not stop "each time". The adopt card says the same (app.js:7081-7088), which is right only because a brought-in run is kept at Step by step (engine.py:5030 pops review_policy). The adopt sheet never says that.
- "Depth and reference brief" disclosure (app.js:4572-4574) holds only "What the brief is about". There is no depth control. README.md:84 ("Depth, extra copies and assistant settings are optional details") and docs/runner.md:152 ("Depth, brand details, extra copies ...") promise one. The brief-kind choice also shows when Reference brief is not selected.
- Yoodli sits under "Extra copies and Yoodli" (app.js:4575-4589), a disclosure named for copies. The Yoodli chip refuses with "Select Reference brief and Practice scenarios first." even though both live in a different card. README.md:192 says only 'choose "Make scenarios for Yoodli" in "New training"'.
- What gets made is split across two controls: the Materials chips (Learner guide, Reference brief, Practice scenarios; app.js:166-167) and a separate "The slide deck" segmented control. The step refusal says "Choose at least one material to make, or a slide deck." (app.js:4766). README.md:84 lists the deck as one of the materials. With a brand shared, the defaults are no materials and a PowerPoint deck (app.js:4261-4275: `materials: []`, `deck` 0), so pressing Continue makes a deck-only training.
- Levels hint: "Choose none for one training without levels." (app.js:4567). The default is 101 ticked (app.js:4268), and the summary says "One training without levels". "Levels" and "level" in "Review level" share a word on the same form.
- NOTICES.stopped/refused (app.js:21-26): "Run the desk command again in your terminal and use the new link." Under the runner, the person opened "Open Training Studio" or `studio`, not `training desk`.

## 1. Broken or dead-end paths (ranked by what a person loses)
1. **No way to add a source once research is planned.** After "That is all of them", engine.py:3793-3794 refuses every add or remove with SETTLED (engine.py:300): "The research for this training was planned from the documents already added, so they cannot be changed now." The research stop's "Ask for changes" sheet (app.js:1368-1420) offers only a note and "Bring the evidence up to date". A forgotten or newer document means deleting the training and starting again, which loses every approval. The same holds for sites: the run pins `research_from` (docs/runner.md:246), and nothing on the page widens it later.
2. **A suite install is told an update is ready and given nothing to do.** When Marketing Studio manages the install, upkeep.py:1229-1230 sets `offered` false and returns `suite: 'marketing-studio'`, and upkeep.py:796-797 refuses with "Update this studio with the Marketing Studio installer." app.js never reads `.suite` (grep finds nothing). So Home's Updates card (app.js:7700-7718) says "Newer versions are ready for this computer:", lists the rows, and offers only Dismiss. It never names the Marketing Studio installer. Status → Versions is the same.
3. **A finished runner training invites a conversation in the runner's private copy.** paintTraining (app.js:3104-3106) shows folderCard ("Carry on with your assistant · Start your assistant in this folder: <workspace copy> · Then say: …") once `run.state === 'done'`. That includes `deck_left`, which DECK_LEFT (app.js:200-201) words as "make the deck with your assistant, or leave it out." This contradicts docs/runner.md:348 ("a training the runner drives should not also be driven from a conversation"). The folder is the runner's own copy in its data folder, its decisions stay on the page, and decisionsCard (app.js:3021-3024) still says "This training runs from this page".
4. **Bring-in refuses a folder that is a git repository.** team.py:356-358 refuses any `.git`, the top folder included: "<name> holds a repository of its own, which a workspace does not take." A person who put their conversation training under git (the README never says not to) has no way forward from the page.
5. **Conversation runs whose documents-scoped plan has not started wait for documents again.** engine.py:5034-5035 marks documents as done only when the plan has started. Otherwise a brought-in training waits on "Add your documents", although its `sources/` folder already holds them; the runner's own document store is separate. Unverified end to end.
6. **Published shows only today's index.** publishedRow (app.js:8133-8141) says "the index here is the training as it stands now, not as it was published". There is no way on the page to read the published revision itself.
7. **The question limits are only checked at Start.** The research-questions hint says "One question a line, at most 8." (app.js:4695). The 300-character limit (pipeline.py:476-477) is never mentioned, and both limits are enforced only after "Start the training". The form keeps the answers, so nothing is lost but a round trip.

## 2. Confusing or contradictory copy (rest)
- **Two names for one thing, stage by stage** (desk.py:73-76 bead names, workspace.py:71-84 labels, the form, README):
  - research-plan: "Questions", "research plan", "Draft the research questions", "The research questions".
  - blueprint: "Blueprint", and "teaching plan" (app.js:4562 "Research and a teaching plan connect every selected material"; README.md:86 "Read the teaching plan").
  - document: "Guide", "learner guide", and "Document" (how-it-works.md:13).
  - brief: "Brief", "Reference brief" (form), "product brief"/"competitive brief".
  - scenario: "Practice", "Practice scenarios", "scenario".
  - package: "Wrap-up", "Package" (how-it-works.md:18), "Write the index", "finished materials".
  - skipped: "left out", while the action says "Skip this stage".
- **Three places change the same shared values.** Settings → "Shared settings" says "Your assistant, work folder, brand and delivery choices apply across all studios." and opens Marketing Studio's /onboarding/ (app.js:2079-2081, 741-743). Set-up's "The agent that does the drafting" (app.js:4078-4080) and its studiosCard say the same values are saved from there (app.js:3943-3953). Settings' own "Brand skill" card says "Every studio on this computer shares the repository and release named here" (app.js:335-340). Nothing says which to use. The same card also names "delivery choices", which Training Studio has no field for (docs/runner.md:133).
- **Two "brand" settings on two screens.** "The brand skill decks are made with" is on Set-up (app.js:4022-4035); "Brand skill" (its repository) is on Settings (app.js:8075-8100). Both are titled after the brand skill.
- engine.py:3791-3792 refuses with "This training is researched from the public web, so it takes no documents." It also says this for sites-only research.
- DELETE_SAYS (app.js:305-306): "It goes from this computer and from your team’s workspace." It says this even when the workspace is a folder on this computer.
- README.md:210 sends issues to github.com/dbbaskette/training-studio/issues. Install, upkeep and guidance all use marketing-studio (README.md:58, upkeep.py:789, sync_guidance.py).
- docs/desk.md is titled "The page", lives at desk.md, and is reached with `training desk`. The runner's page is the same page (page.py:1-5 "the desk's page"), but it opens through `studio`. README.md:218 calls the doc "The page in a conversation". The word "desk" names the conversation-mode server and the page code, and Blog Studio now uses it for its writing desk.
- docs/desk.md:68 says "Settings holds notifications and where each training is decided." That is true only without the runner. With it, Settings holds 10 cards (app.js:2077-2096).
- docs/desk.md:85 says "It does not start or run a training. Your assistant does that." The same page started from `studio` does both, and the doc does not say so.
- The run says "Stop ends the step in hand and loses its work so far; Pause lets it finish first." (app.js:4956-4957), and the Stop toast agrees (app.js:131-132). Fine. But Stop sits in the toolbar as a quiet button beside Pause, with no confirmation, although it loses work.
- RUN_WORDS.elsewhere is "Run from another computer" (app.js:123), while the list heading is "Run by your teammates" (app.js:1742) and the run callout is "<name> is running this training" (app.js:6983).
- The finished-run copy says "Ready to use" / "Not ready to use yet" (app.js:5729-5741). The training card says "Finished, but not ready to use" (app.js:4913-4914). Home's heading is "Finished" (app.js:1743), and it also lists trainings that are not ready.
- The Shared settings link (app.js:2080) changes `location.href` to /onboarding/ in the same tab. It is a quiet button inside a card, not a link, and nothing says it leaves Training Studio.

---
# Sections 1–2, part B (blueprint to package, copies, review levels, stops)
# FINAL (supersedes draft notes above)

## 1. Broken or dead-end paths (ranked by what a person loses)

1. **Google Doc edits cannot be brought in unless the local file also changed.**
   "Bring the Doc's changes in" is drawn only when `found.conflict` or the problem starts
   "Someone has changed the Google Doc" (app.js:5570-5573). That problem only arises when a
   push is attempted, and `copies.make` pushes only copies that are not `made`
   (runner/copies.py:117-120), i.e. when the local file changed. `gdocs.copy_states` never
   asks Google (gdocs.py:375-392). So a reviewer's edits in the Doc on an unchanged, approved
   guide/brief are invisible: the copy says "Made", no pull button. When the button does
   appear, local changed too, so the pull always ends in the both-changed conflict
   (copies.py:213-227), never a clean pull. The core round trip is effectively unreachable
   from the runner page. docs/runner.md:193 promises the button unconditionally.
2. **Final-review download saves files with no extension and a sentence for a name.**
   app.js:6309-6310 passes `item.label` ("the level 101 slide deck") as `link.download`
   (app.js:905); a blob URL ignores the server's Content-Disposition (runner/page.py:300-302),
   so the deck/guide downloads as "the level 101 slide deck" with no `.pptx`/`.md`.
   Toast: "Downloaded the level 101 slide deck." Elsewhere (app.js:5276-5277) the name is the
   file's basename, so 101 and 201 guides both arrive as `document.md`, and every index as
   `README.md` (app.js:8212-8213); the server's training/level-prefixed name is lost.
3. **A deck waiting for a picture offers the wrong action and no way past it.**
   ASSETS_WAIT (engine.py:322, 2151-2152) uses the default action `retry`, so the stop's
   filled button is "Try again" with "Try again re-runs this step from the start…"
   (app.js:5013-5016), titled "It is waiting for you". The real action, "Supply the
   picture"/"Add the picture", is in the deck card far below (app.js:5948-5966, card order
   app.js:6436-6438). There is no "draw it without this picture": a person without the
   screenshot can only skip the whole deck or Redesign.
4. **"Ask your assistant…" dead ends inside the runner.**
   - copies.py:63-66: a missing Doc says "Ask your assistant to unlink it from the
     training, then try the copies again" — the runner has no assistant and no unlink on
     the page.
   - pipeline.py:98-104 DECK_LEFT/DECK_AGAIN and app.js:200 "make the deck with your
     assistant": a runner training lives in the runner's own workspace copy, is decided on
     the page, and runner.md:349 says it "should not also be driven from a conversation".
   - app.js:3103-3105 shows "Carry on with your assistant" (folderCard) on every finished
     runner training, pointing an assistant at the runner's workspace folder.
5. **A late change at the finished-materials review silently re-opens the first-drafts
   review.** reviews.py:345-347 drops the `direction` approval for any target but
   scenario/Yoodli; under Balanced, asking to change one guide at the final review means
   "Review the first drafts" (all levels) again, the deck redrawn, its gate, then final again.
   The request hint says only "If it changes, these are written again from it: …"
   (app.js:6324-6326); nothing warns of the extra stops.
6. **Any change to a drawn deck rewrites the words and redraws everything.** A request on
   the deck re-drafts the outline (pipeline.py:1105-1115) and every later step. There is no
   slide-level fix; the gate's generic hint "Training Studio makes the change and brings it
   back here." (app.js:50 via 1394-1395) hides that; only the price line hints at it.
7. **Pulled Doc headings that lost their `covers` note are dropped silently.** gdocs.pull
   returns `unplaced` (gdocs.py:333-336) but copies.pull returns only `result`
   (copies.py:234); the person later meets a failed coverage check with no explanation.
   docs/google-docs.md:63 says "Your assistant tells you which one".
8. **Brief/practice cannot be skipped while Yoodli is on, and nothing says why.**
   desk.py:511-513 withholds `skip`; the gate's More menu simply lacks "Skip this stage".
9. **"Could not be used" stops send the person to Status with no button.** stops.unusable:
   "Check this computer, on the Status screen, says what it needs." (core stops.py) but the
   stop offers only "Try again" (engine.py:1338 label; app.js:5139-5141).
10. **"A scenario of your own" has no page path.** runner.md:231 ("A scenario file you wrote
   in the training's folder is used as it is") and WHOSE.you (app.js:208-211) describe it,
   but the form and run have no scenario upload; the folder is the runner's internal copy.
11. **Missing intake is a hard dead end.** pipeline.py:1278-1279 "…Start a new training in
   its place." with action None → only "See everything it made" (app.js:5139-5142).

## 2. Confusing or contradictory copy; two names for one thing

### Contradictions (ranked)
1. **Automatic draft's stops, said two ways on one card.** REVIEW_SAYS.automatic "Stops only
   for the finished materials." (app.js:175) sits under the line "Automatic draft: it stops
   for each drawn deck and the finished materials" (app.js:4673-4678) in reviewLevelCard
   (app.js:4606-4608). Code stops at each drawn deck (deck_flow.py PAUSES/GATES;
   review_policy.automatic). REVIEW_SAYS.balanced (app.js:172-173) also omits "each drawn
   deck". README:3, runner.md:162 match the code.
2. **Where briefs come.** app.js:4683-4685 "Review the first drafts comes after research and
   the blueprint, guide and brief for each level" — layout 2 (all new runs) prepares no brief
   first (reviews.py:12 DIRECTION_PREPARED); runner.md:197 and how-it-works.md:493 "Briefs
   are written afterwards".
3. **Google Doc pull in the runner.** runner.md:193 "A Google copy has Bring the Doc's changes
   in" vs runner.md:348 "Bringing edits back from a Google Doc … are not in the runner yet."
4. **Deck cost: history or estimate?** deckCard/costBefore "A deck of this size has cost about
   $X … before." (app.js:5893-5900, runner.md:205 "what a deck of this size has cost before")
   vs commitsSays "(a fixed estimate, not this computer's history)" (app.js:6072-6074). It is
   a fixed per-slide rate (deck.py:595-599).
5. **Walkthrough "one at a time" vs one decision.** Form hint "Choose this to approve how each
   slide is drawn, one at a time." (app.js:4548-4549) vs runner.md:207 "It is still one
   decision" and the outline screen approving all slides together (app.js:6668-6670).
6. **Stop count overcounts.** engine.py:1049-1055 promises 3 stops for Balanced (+decks);
   documents-only Balanced accepts the form-written plan (engine.py:3264-3265), so the run's
   "it stops and asks for your decision at least 3 times" (app.js:4975-4977) is one too many;
   the form itself gets this right (app.js:4667-4672).
7. **"Carry on in the brand's default look" does two different things.** On the run it acts
   at once (app.js:5857-5859); in "Review the first drafts" it is a toggle that only arms the
   approval (app.js:6287-6291).
8. **Download/copy limitation vs blocker.** Copies card "A copy that is not made is listed as
   a limitation." (app.js:5660-5661) is right for a missing copy but an out-of-date one blocks
   readiness (checks.py:688, 701); finished_says appends "A copy this training asked for is
   not made. Try the copies again." (pipeline.py:1340-1341) for both.
9. **Form has no "deck step".** runner.md:219 "The deck step asks How is this deck used?" and
   :221 "on the deck step" — the form's steps are "Learning goal, Materials, Review and
   start" (app.js:153); both controls are on Materials.
10. **"Approving finishes this draft"** for the whole finished training (app.js:6060,
   6244) — "draft" names the finished materials.
11. **Lower-case sentence start:** copies BOTH "{label} was changed here…" renders "the level
   101 learner guide was changed here…" (copies.py:183, engine.py:3901).
12. Stop vs docs: STEERED.stop "its work so far is lost" (app.js:131-132) vs runner.md:266
   "Everything already kept stays" — compatible, but only the page says the step's work goes.

### Two (or more) names for one thing
- **Deck outline:** "what the deck says" (app.js:5810-5813, 6634), "Deck direction · Level
  101" (reviews.py:312), "the direction" (reviews.py:403-404 "before you approve the
  direction"), "Wireframe draft of the deck" (app.js:5830), "draft" (deck_flow checkpoint),
  "outline" (runner.md:166-168 "its outline"), "the words" (runner.md:211). "Direction" also
  names the first-drafts review (`review:direction`, engine.py:304 "first drafts review") and
  the brand look (`deck_direction`). Engine error reads "Pick a look for deck direction ·
  level 101 before you approve the direction." (reviews.py:403-404).
- **First-drafts review:** "Review the first drafts" (step label, reviews.py:114), "first
  drafts review" (engine.py:304; standing button "Request changes in the first drafts
  review", app.js:2414-2416), "Approve the first drafts" (app.js:6035), "the direction"
  (runner.md:195), "teaching plan" review (runner.md:161).
- **Final review:** "Review the finished materials", "final review" (engine.py:304,
  app.js:5690 "The final review waits…"), "finished-materials review" (runner.md:195),
  "Done" (how-it-works.md:495).
- **Guide:** "learner guide" (workspace.py:72), bead "Guide" (desk.py:74), file/stage
  "document" (README:123), "The document" pane (app.js:2205).
- **Brief:** "brief", "Reference brief" (app.js:157), "product brief"/"competitive brief"
  (README:14), "knowledge brief" (form hint app.js:4590).
- **Blueprint:** "blueprint", "teaching plan" (app.js:4537 "Research and a teaching plan
  connect every selected material"), "teaching blueprint" (runner.md:147).
- **Practice:** "Practice scenarios" (form), bead "Practice" (desk.py:75), "practice
  scenario" (workspace.py:73), "scenario".
- **Yoodli output:** "Yoodli scenario" (workspace.py:74, README:194), "Yoodli field layouts"
  (app.js:4651, pipeline.py _about), "Yoodli layouts" (app.js:6066), "Yoodli fields"
  (how-it-works.md:495), "Yoodli handoff" (checks.py:693); AHEAD "Build {the} Yoodli
  scenarios" (workspace.py:83) though nothing is built in Yoodli.
- **Package:** bead "Wrap-up" (desk.py:76), step "Write the index" (workspace.py:83),
  "package" (how-it-works.md:357), "The index", README.md; finished states "Finished here"
  (app.js:118), "Finished", "Ready to use", "Finished, but not ready to use".
- **Leaving the deck out:** "Skip the deck for now" (app.js:5703), "Leave the deck out"
  (app.js:5675), "Skip this stage" (gate menu), "No deck" (form).
- **Research plan:** "research plan", bead "Questions" (desk.py:73), "research questions".
- **Intake:** "intake summary" (workspace.py:71), bead "Start" (desk.py:73).

### Also noted (out of slice)
- Matrix (docs/superpowers/plans/2026-10-20-training-workflows.md) has no rows for Google Doc
  pull/choose, supplying a deck picture, Redesign, or looks that could not be rendered,
  though each changes status/inputs (AGENTS.md "State changes need a matrix row").
- Phone-only "Looks good" chip (app.js:6343-6348) means "N of M looked at" counts only on a
  phone.

---
# Section 3 (cleanup)
## 3. Cleanup (Training Studio)

### 3a. Helpers duplicated from core/studio_core (safe now; no saved-training impact)
1. `skills/training-studio/scripts/desk.py:700-737` class `Desk` is core `server.Desk`
   (`core/studio_core/server.py:431-470`) word for word but one docstring word; `desk.py:617`
   `text()` = `server.py:107`. desk.py already builds `_security` from `server.for_product`
   (desk.py:58-65) and takes Refusal/Server/Handler from it, so `Desk`/`text` can be taken too.
   Also dead: desk.py:41-47 `SECURITY_HEADERS` dict is overwritten at desk.py:65; desk.py:30
   `HOST`, :40 `JSON` only feed the duplicated Desk. Blank-line debris at desk.py:89-96.
2. `skills/training-studio/scripts/cmd_desk.py:8-48` `NOT_A_PERSON`, `interrupt`, `port`,
   `has_a_screen`, `show`, `announce` duplicate `server.py:119-155` (same code). Safe now.
3. `runner/setup.py:246` `same_address` = `core/studio_core/workspace_setup.py:22`. Safe now.
4. `runner/claude-code-models.json` is a second regular-file copy (byte-identical today) of
   `studios/presentation/runner/claude-code-models.json`, which `core/studio_core/claude-code-models.json`
   symlinks to; `runner/settings.py:84,161-200` `CLAUDE_MODELS`/`claude_models`/`read_models`
   re-implement `core/studio_core/model_catalog.py:68` `claude_models`. Two lists can drift;
   docs/runner.md:350 tells people to edit "that file alone" (the Training copy) and
   tests/test_runner_agents.py:838,846 pin that path. Fold into model_catalog; update the
   doc line and test together. No saved-training impact (runs pin model names, not the list).
5. Cross-studio copies outside core (not core duplicates, but the same port): `runner/gitstate.py`,
   `team.py`, `agents.py`, `worker_tools.py`, `slides.py`, `brand.py`, `research.py`,
   `documents.py` were ported to Presentation Studio (studios/presentation/docs/superpowers/plans/2026-10-14-presentation-studio.md:60,233).
   Out of this slice; candidates for core once the desks land.

### 3b. Legacy paths for old runs (what saved trainings need; how to tell)
All run-record checks read `<training>/.training-studio/run.json` (engine.py:219 `RECORD`).
None of these can be removed on a code read alone: a scan of every known workspace
(`training.py list` + each runner workspace) is needed first, and two are not "old runs only".

1. **Legacy research question queue** (biggest code weight: `briefs/research-plan-queue.md`,
   `briefs/research-question.md`, pipeline.py:1429-1515 plan/question work, engine.py
   research branches at 3256-3296, 3391-3410, 3518-3538, 4036-4071, `research_contract.LEGACY_JOBS`
   at engine.py:429, workspace.py:766-785 schema-1 `research_record`).
   - Not old-runs-only: engine.py:1023-1029 snapshots the contract at start and silently
     falls back to the queue when `research_contract.snapshot()` returns None, i.e. any NEW
     training on a computer whose Harness Research lacks `scripts/lib/synthesis-cli.mjs`
     (core/studio_core/research_contract.py:129-150). Nothing refuses an old helper at
     start (the conversation path does refuse: workspace.py:752). So docs/how-it-works.md:363
     and docs/runner.md:380 "It can go once no workspace holds such a run" is wrong today.
   - Also brought-in conversation trainings without a contract (engine.py:5031-5033).
   - To retire: (a) refuse Start with "Update Harness Research" when snapshot is None
     (pins/companions.json already requires >=1.0.0); (b) scan for run.json with no
     `research_contract` whose `steps` lack a finished `research` step. A legacy run already
     past research still needs `research_record` (workspace.py:780) to read its record
     for staleness and the index, so keep the reader, drop the writers.
2. **Review layout 1** (`review_layout` absent → 1, runner/reviews.py:17-22; engine.py:4401;
   page.py:34). Layout 1 writes briefs before the first combined review (`PREPARED` incl.
   'brief'). Saved trainings need it while any run.json lacks `review_layout` AND has a
   non-step-by-step `review_policy` AND has not passed `review:final`. Small code; low value
   to remove.
3. **No `review_policy` → Step by step** (core/studio_core/review_policy.py:71-74). Not
   legacy-only: `_brought` deliberately pops it for trainings brought in from a
   conversation (engine.py:5026). Keep.
4. **Run-record schema 1/2/3 acceptance** (engine.py:386-393). `new_record` still writes
   `SCHEMA = 1` (engine.py:218,411) and bumps to 2/3 in place (engine.py:1022-1029), so all
   three are current shapes, not legacy. Keep; but "SCHEMA" naming is misleading.
5. **Research scope words** (`research_from` absent → `research_sites.legacy(scope)`,
   pipeline.py:503-512; `scope_of` pipeline.py:495 "older words ... which the rest of the
   runner still reads"; LEGACY_DOCUMENTS/BOTH in core/studio_core/research_sites.py:29-30).
   New runs always pin `research_from` (engine.py:420). Old runs need the reader; the
   internal `source_scope` strings could be dropped only if every caller read `research_from`.
   Tell: run.json without `research_from`.
6. **Deck delivery default 'reading'** for trainings saved before delivery was asked
   (runner/deck.py:95 `DELIVERY`). Tiny; keep while any session `settings` lacks `delivery`.
7. **Pre-0.16 Harness Slides branches.** slides.py:186 refuses any tool older than 0.16.0,
   yet slides.py:81-145, 579-776 still branch for "a tool that lists none" (0.13.1) and
   "the way before" 0.14.1 capabilities (engine.py:76-82). Unreachable with a real tool if
   0.16.0 lists every capability in tests/stand_ins/slides.py:136 `CURRENT`; confirm
   against the pinned 0.16.0 `version` output, then remove the branches and the stand-in
   modes `stand_in(current=False)` that play "0.16.0 listing nothing" (stand_ins/slides.py:37-46).
   Saved decks do not need them: a deck "carries on as it began" only in its gate shape
   (designed True/False), not in tool version. ~148 test references to 0.13.1/0.14.1/
   no-capability tools across 8 test files (test_runner_slides.py, test_runner_deck.py,
   test_runner_deck_whole.py, test_desk.py, runner_support.py, ...).
   NOT legacy: `designed is False` (words-only deck gate) — it is the default for every new
   deck because the walkthrough is off by default (pipeline.py:446-449, 589); and `redesign`
   (engine.py:2839) is its upgrade path. Keep both.
8. **critic.LEGACY questions** for deck review rounds saved before rounds recorded their
   questions (core/studio_core/critic.py:18,30,61-64; deck.py:1125,1276,1321). Needed only to
   re-read old rounds at an old deck's gate; tell: a round's critic.json without questions.
9. **Settings migration "From an earlier version"** (settings.py:446-464 `own`/`forget_own`;
   gitstate.py:178-190 `own_share`/`forget_own_share`; docs/runner.md:141). Per computer, not
   per training: needed until every install has started once on a version with it. Tell:
   runner.json holding agent/model/effort/brand_*/previews, or the workspace record holding
   `share`. Safe to drop after a release or two; no training loses anything.
10. **Balanced research-plan stop applied to older runs** (core/studio_core/review_policy.py:132
    and README.md:3, runner.md:170-173). A rule, not a branch; the README sentence can go once
    no Balanced run is before its plan.
11. **Old run-question docs**: "an earlier training researches each question, several at a
    time" (runner.md:178), "A research question that fails three times..." (runner.md:343):
    describe item 1 only.

### 3c. Dead code and unused routes
- Routes: every `/api/*` path in runner/page.py:182,230 and desk.py:55-56 is called by
  desk/app.js (via `ask`/`call`/`reach`, app.js:840-870; `drive` through app.js:7165,
  `deck-draft` through the ticket at page.py:682). No dead route found.
- Functions: no top-level function in runner/*, runner/briefs, scripts/*, installer/* is
  unreferenced (scripted scan; only overrides such as `read_framed`, HTMLParser hooks).
  No unused function or constant in app.js.
- Real dead weight is the duplicated helpers (3a) and unreachable branches (3b items 1, 7).

### 3d. Tests for removed or legacy-only behaviour
1. **The research stand-in is the legacy queue CLI** (tests/stand_ins/research.py:1-8:
   "plan, record and status"; no synthesis). So the runner journey suites
   (test_runner_flow.py, test_runner_research.py, test_runner_pipeline.py, test_runner_page.py,
   test_runner_documents.py, ...) exercise the legacy question queue, while today's synthesis
   path is covered only by test_runner_engine.py (38 mentions, by setting
   `record['research_contract']` and mocking `research_contract.native`, e.g. :998-1008) and
   test_synthesis_integration.py, which is skipped unless `STUDIO_TEST_RESEARCH_RUNTIME` is set
   (:35). Retiring the queue first needs a synthesis stand-in; then ~these suites move to it.
   This is also the main coverage gap: the path every new training takes is the less-tested one.
2. **Pre-0.16 Harness Slides stand-ins**: tests/stand_ins/slides.py:37-46 plays "0.16.0 that
   lists no capabilities" (`listed=None`, `release=MINIMUM`) and 0.13.1/0.14.1 modes, a tool
   the runner can never meet (slides.py:186 refuses older). ~148 references in 8 files.
   Remove with 3b item 7.
3. `test_review_levels.py:47` pops `review_layout` to test layout 1; keep while 3b item 2 stays.
4. Matrix row "Legacy form omits materials" (docs/superpowers/plans/2026-10-20-training-workflows.md:55;
   pipeline.py:598 defaults `materials`) guards an API caller without materials; the page
   always sends them. Keep only if old open tabs matter; otherwise drop row + test together
   (AGENTS.md: state changes need a matrix row).
5. tests/test_runner_agents.py:838,846 pins the duplicate `runner/claude-code-models.json`
   and the doc sentence; change with 3a item 4.

### 3e. Stale docs, README and guidance
Ranked by what a reader loses.
1. docs/runner.md:348 "Bringing edits back from a Google Doc ... are not in the runner yet"
   contradicts runner.md:193 and how-it-works.md:495 (pull exists). Delete the first half.
2. docs/how-it-works.md:363 and docs/runner.md:380 "The legacy question queue ... can go once
   no workspace holds such a run": false while an older Harness Research silently starts new
   runs on it (3b item 1).
3. skills/training-studio/references/levels.md:22 "If the levels together need more than 30
   questions, propose splitting" contradicts stages/research-plan.md:35,56 (1 to 8 for
   synthesis). A conversation run is told two limits.
4. README.md:210 issue link `github.com/dbbaskette/training-studio/issues`: the code and
   guidance now live in marketing-studio (sync_guidance.py:32, upkeep.py:789).
5. README.md:3 is a ~200-word paragraph on review levels, research-plan stops for older runs
   and deck holds; AGENTS.md says the README is for a new user. Move to docs/runner.md.
6. docs/desk.md describes the conversation-only page (`training.py desk`, its 7 routes,
   desk.md:292-296 "Settings holds notifications and where each training is decided",
   "It does not start or run a training" :313) while the same app.js is the runner's page
   with ~40 routes (page.py). README.md:121,218 link it as "the page". Also the name "desk"
   collides with the planned training desk.
7. docs/runner.md:201-217 describes the slide-design session as the norm ("You decide three
   times", "Each slide's words sit beside its design"), but runner.md:221 says the
   walkthrough is off by default; reorder so the default path comes first.
8. docs/acceptance.md:9-30 records 2026-10-12 runs on harness-research 0.8.0 with 26
   questions; mark as historical (pre-synthesis).
9. docs/development.md:3,237-243 and how-it-works.md:3 point to the 2026-10-12/13 specs as "the
   specification"; they predate review levels, combined reviews, synthesis research and sites.
   Say they are history, or name docs/runner.md as current.
10. docs/how-it-works.md:349 "Up to 8 synthesis questions; 30 in legacy queues" and
    stages/research-plan.md:35,56 "a saved legacy queue allows 30" carry legacy detail into
    reader-facing tables; trim once the queue goes.
11. runner/engine.py:76-82 module notes ("What Harness Slides 0.14.1 lists beyond that is used
    ... the way before it where it does not") and slides.py:81-145 describe sub-floor tools.

**Guidance near budget** (validate_package.py passes, `--measure`, Python 3.11):
- Files (budget 1000): profiles/yoodli.md 997, SKILL.md 992, references/workspace.md 992,
  references/google.md 982, stages/research-plan.md 980, stages/deck-handoff.md 940.
  assets/examples/yoodli.md 1119/1200.
- Loading sets: `levelled-blueprint` 3988/4000, `google` 1974/2000, `hub` 1919/2000,
  `start` 1839/2000, `stage:brief` 3345/3500.
- Any desk-related guidance (section notes, selection edits) cannot be added to SKILL.md or
  workspace.md without cutting; dropping legacy-queue lines from research-plan.md (:35,:56)
  and research-handoff.md:33-51 ("Existing legacy research") frees room.
- runner/briefs/*.md have no budget check; deck-outline.md is 1264 words, yoodli.md 1038.
  (research-handoff.md "Existing legacy research" is still needed by conversation trainings
  begun before synthesis; trim only after the same scan.)

### 3f. Safe now vs needs saved trainings
- **Safe now** (no saved-training effect): 3a items 1-4 (take Desk/text/cmd_desk helpers/
  same_address/model list from core); desk.py dead `SECURITY_HEADERS`; docs 3e items 1, 3, 4,
  5, 6, 7, 9, 11; the README issue link.
- **Safe after confirming the pinned tool**: pre-0.16 Harness Slides branches and their
  stand-ins (3b item 7, 3d item 2): check that 0.16.0's `version` lists every name in
  stand_ins/slides.py `CURRENT`.
- **Safe after a release or two**: settings/share migration (3b item 9).
- **Needs a workspace scan first** (run.json fields): legacy research queue writers
  (no `research_contract`, research not done) — and first refuse Start on a pre-synthesis
  Harness Research and add a synthesis stand-in; review layout 1 (no `review_layout`,
  non-step-by-step, before `review:final`); `research_from` reader; deck `delivery` default;
  critic.LEGACY rounds.
- **Keep** (not legacy): no-`review_policy` → Step by step (brought-in trainings);
  schema 1/2/3; words-only deck gate (`designed is False`, the default) and Redesign.

---
# Section 4 (layout)
## 4. Layout-rule gaps, screen by screen (Training Studio page)

Page: studios/training/skills/training-studio/scripts/desk/app.js (one controller for the
conversation-mode page and the runner), index.html, style.css (byte-identical to
ui-kit/style.css), plus core/studio_core/deck_web/deck-panels.{js,css}.
Rules: docs/design/golden-gate.md:51-67.

### Shell-wide (affects every screen)
- Phone, fixed bar behind the tab bar: the combined review's send bar `.review-bar` is
  `position: sticky; bottom: 0; z-index: 1` (ui-kit/style.css:2760-2768); the phone tab bar
  (`.sidebar`, fixed, z-index 6, ui-kit/style.css:2204-2217) covers it. The bar that sends
  every marked request sits under Home/Trainings/Status/Settings on a phone. Rule: "fixed
  bars sit above the tab bar".
- Phone, controls under 44px: `.link` 1.75rem (ui-kit/style.css:614), `.seg-option` 2.3rem
  (:675), `.chip` 2.4rem (:1341), `.menu-item` 2.4rem (:715). Training uses all four:
  every toolbar secondary folds into `.menu-item`s on a phone (app.js:755-770 foldActions);
  "See the details"/"Check it on the status screen" are `.link` (app.js:1712); research
  source chips, material chips and review-level segments are `.chip`/`.seg-option`.
- Toolbar order: actions are passed secondary-first, primary-last on Home
  (app.js:1748 `actions: [start, lead]`) and Trainings (app.js:1789-1791 Published then New
  training). Rule order is title, primary, then quiet secondaries; Blog puts the filled
  one first (studios/blog/.../management/app.js:62-69).
- Card headings: list cards use `h2.row-title`/`h2.invite-title`, not `.card-title`
  (app.js:1677, 1757); rows inside a card use `h3.row-title` (app.js:1613, 1639), giving two
  heading levels per card.

### Screens, ranked by what a person loses

1. **Combined reviews (Review the first drafts / finished materials)**, run screen part
   `combinedReview` app.js:6237-6362, bar `reviewBar` app.js:6204-6235.
   - Primary does not follow the work: the toolbar's filled "Approve the first drafts" /
     "Approve the finished materials" (app.js:5773-5777) stays filled after items are
     marked "Needs changes"; the action the person is now taking, "Send N requests", is a
     plain button in the bar (app.js:6211). The approval sheet only warns afterwards
     (app.js:6099-6100).
   - Phone: the bar is covered by the tab bar while reading (see shell-wide); the phone-only
     plain "Approve…" copy in the bar (app.js:6213) is behind it too.
   - The lede sits inside the card, not as the page's `.lede` (app.js:6242); the run's own
     lede comes earlier in `runIntro`, so the screen has two ledes.
   - Marks differ by width: "Looks good" exists only on a phone (app.js:6339-6346), so a
     desktop reader cannot record "looked at", though the bar counts "N of M looked at".
   - Every material is a disclosure inside one card; the look picker, wireframe panel,
     slide pictures, downloads and the note box all nest in a `<details>` (no
     `.sheet-part`/`.card-title` structure), so a deck item has three or four
     action rows ("Try again", "Carry on in the brand's default look", "Open the saved
     deck and its review", "Download …") inside a disclosure.
2. **Run / watching a run** `paintRun` app.js:6364-6456, `runActions` app.js:5772-5807.
   - The one primary moves between toolbar and body: for review, outline, combined, resume,
     retry and "Open the index" it is in the toolbar; for a question ("Send answer",
     app.js:5172), a problem's action (app.js:5139), documents ("That is all of them",
     app.js:5528), the look ("Use this look"/"Try again", app.js:5855-5861) and "Take it"
     (app.js:6974) it is in the page, with nothing filled in the toolbar. "Use this look" is
     filled unconditionally, so a look and a problem together give two filled buttons.
   - Order breaks "what needs you first": part order (app.js:6394-6452) puts the whole
     combined review above a worker's question (`question` after `combined-review`); a deck
     waiting for a picture is asked inside `deckCard` (asset form app.js:5948-5966, plain
     "Add the picture"), below Steer it and Finished, with no lead and no toolbar action;
     a Google copy conflict ("Use the Doc's version" / "Keep this version and send it",
     app.js:5560-5568) sits in Copies, after Workers and Steps (the production log).
   - Secondaries are not quiet: Pause, Resume, "Review X" when not lead, "Open the index"
     are plain capsules; only Stop is quiet (app.js:5788-5803). Toolbar order is
     primary-last.
   - Lede is not first: `runIntro` puts the decided line, now-line, state, beads and the
     queue line before `p.lede.run-says` (app.js:4939-4949).
   - Picture supply is a four-field form inside a list row (file, What it shows, Where it
     came from, Any limit) — a "make something" input that the rules would put in a sheet
     with numbered steps.
3. **New training** `paintNew` app.js:4703-4735, steps app.js:4450 (Learning goal), 4526
   (Materials), 4641 (Review and start).
   - Submit is not at the form's end: the visible "Continue"/"Start the training" is only
     in the toolbar (app.js:4716); the form foot holds "Back a step" and a hidden submit
     (app.js:4720-4728). After scrolling step 3, the person finds no Start button.
   - Step 3 "Review and start" is a summary first, then new inputs: "Ready to start"
     (app.js:4689) precedes "Where this training stops", "Sources" (Research from, Your
     sites, Add a site, research questions) and "Assistant and limits". The form does not
     run in the order it is filled, and the summary describes choices made below it.
     Blog's start puts sources and settings in their own step before Start.
   - No `.lede` on any step (the step title is in the toolbar, "New training · Step n of 3"
     above it).
   - Step 2 packs materials, levels, deck, delivery, walkthrough, brand, time and two
     disclosures into one card "What would you like to make?" (app.js:4571-4593) with no
     sub-heading or hairline between groups; Yoodli hides under "Extra copies and Yoodli"
     though it depends on two chips above it.
4. **Gates** (research plan, research, blueprint, guide, brief, scenario, Yoodli, deck)
   `paintGate` app.js:2516-2551, `gateActions` app.js:2478-2513; **What the deck says**
   `paintOutline` app.js:6622-6676.
   - No lede for most gates: `.lede` is drawn only for a scenario's ownership or a deck's
     pictures (app.js:2530-2532); research, blueprint, guide, brief and Yoodli gates open
     with a state and beads, no sentence saying what to decide.
   - "Ask for changes" is a plain (not quiet) capsule; toolbar order is
     Ask for changes, More, then the filled Approve (primary last) (app.js:2490-2512,
     6670-6672).
   - Phone: gate actions are not folded (only the run uses `foldActions`); More's
     `.menu-item`s are 2.4rem.
   - Combined-covered gate: no toolbar action; the way out is a plain button in a callout,
     "Request changes in the …" (app.js:2416-2418).
5. **Home** `drawHome` app.js:1720-1751.
   - Order: "Updates" (versions, Upgrade, Install the brand skill) and "Your other studios"
     cards come before Needs you (app.js:1735-1736). Rule order puts setup after
     needs-you, in progress and start-new.
   - No `.lede`: the greeting is a `.large-title` under a toolbar already titled Home
     (app.js:1735); no "ways to start" section (Blog Home has one) — New training is only
     the toolbar button, plain when something needs you.
   - Toolbar: New training before the filled Review/Open (primary last).
   - Lists: every finished training stays on Home with no cap or search.
6. **Training detail** (conversation-mode and runner) `paintTraining` app.js:3071-3111.
   - Order: Files table comes before "In the way" (app.js:3097-3099); "In the way",
     "Left out or limited" and "Warnings" are always drawn, even empty ("Nothing is in the
     way.", "No warnings."), three empty cards.
   - Toolbar: plain "Watch the run" before the filled "Review X" (app.js:3091-3094).
   - Cards nest `h3.row-title` under `.card-title` ("Left out", app.js:3035).
7. **Trainings** `drawTrainings` app.js:1772-1792; **Published** `paintPublished`
   app.js:8148-8165; **Status** `drawStatus` app.js:1996-2020.
   - No filters on any list: Trainings, Published and Status have no search row, though a
     team workspace lists every teammate's training too.
   - Trainings cards title with `h2.row-title`, not `.card-title` (app.js:1757); the
     Open is plain, Delete quiet — fine.
   - Status: no `.lede`; the table (one Open per row, data-labels for phone) is fine; the
     "This computer" card that names what needs putting right is last, after Versions
     and Skills (app.js:2003-2009).
8. **Settings** `drawSettings` app.js:2074-2097.
   - No `.lede`. Order mixes kinds: Shared settings, Where new work stops, Workspace, then
     "Preview files in your Google Drive" (housekeeping) before Notifications, Updates and
     Brand skill; the per-training "Where each training is decided" is near the end.
   - The only filled button is "Turn on notifications" in a card (app.js:2039); "Check and
     save" (Brand skill) is plain. "See the versions" appears twice (Updates and Brand
     skill cards, app.js:8070, 8097).
   - "Change shared settings" (quiet) leaves the page for Marketing Studio's onboarding in
     the same tab (app.js:2083); "Change the set-up" in Workspace also edits the agent
     (two places for one value; copy issue, outside this section).
9. **Set-up** `paintSetup` app.js:4068-4094 — closest to the rules (lede, submit + Cancel
   at the end, Back only when reached from Settings). Gaps: "Checked for you" is an h3
   inside the place card (app.js:3933); limits fields are short inputs with no unit
   suffix.
10. **Index** `drawIndex` app.js:8197-8221: no lede; "Download the index" is a quiet button
    under the document rather than in the toolbar (the screen has no primary).
11. **Sheets** (Approve/Ask for changes/Rebuild/Skip/Accept `confirmSheet`/`noteSheet`
    app.js:1346-1423; Done `afterSheet` 1425-1448; team take/hand over/publish/run-from-here
    `teamSheet` 7149-7158; delete 7284-7320; redesign 7383-7398; upgrade 7764-7792; brand
    7820-7839; companions 7998-8016; copy choice 5588-5600) — follow the rules: glass,
    `.sheet-part` sections, submit then Cancel together, toolbar actions hidden while open.
    Done's "Watch it carry on" is a plain middle button between filled and quiet (fine).
    None makes something, so numbered steps do not apply; the only "make" inputs (picture
    supply, Add a site, Add documents) are inline, not sheets.
12. **Glass**: respected. Only `.sidebar.glass`, `.toolbar.glass`, `.sheet.glass` and
    `.toast.glass` (index.html:20, 32, 39; app.js:940); cards, forms, reviews and slide
    strips are opaque (`.shine::after` is disabled, ui-kit/style.css:328).

### Shared file note
desk/style.css is a byte-identical copy of ui-kit/style.css; Blog vendors it with a pin
(studios/blog/.../management/training-studio-ui.json, pointing at the old training-studio
repository). Fixing the phone sizes or the review-bar offset in ui-kit needs the copy
re-synced (cleanup section's concern).

---
# Section 3 addendum (found while mapping section 5)

- **The runner is a fork of Presentation Studio's runner, not a user of core.** These files
  share most of their lines with studios/presentation/runner/ (unique lines in common /
  Training lines): brand_source.py 313/364, companion.py 205/249, agents.py 596/741,
  upkeep.py 973/1354, gitstate.py 579/791, brand.py 339/426, documents.py 442/575,
  research.py 107/143, slides.py 629/893, team.py 264/377, worker_tools.py 1347/2319,
  setup.py 427/719, settings.py 301/464. Each fix lands twice or drifts. Moving the
  identical parts into core/studio_core is safe for saved trainings (no record format
  changes) and should come before any deck desk, which would otherwise be built twice.
- `scenario:*` lists no upstream (workspace.py:390-392): a blueprint change never marks a
  scenario out of date, although scenarios are drafted from the blueprint's practice plan.
  Yoodli does track blueprint + brief + scenario (workspace.py:395-397).

---
# Section 5. A training desk, in depth

Paths: T = studios/training, R = T/runner, S = T/skills/training-studio/scripts,
B = studios/blog/skills/blog-studio/scripts, C = core/studio_core.

## 5.0 Naming first
"Desk" already means Training Studio's whole page: S/desk.py, S/desk/app.js,
`training.py desk`, docs/desk.md ("The page"), and R/page.py:1 ("the desk's page"). Name the
new screen something like "the training desk" in the copy, and give the new modules other
names (for example `R/workbench.py`). Otherwise retitle docs/desk.md and rename S/desk.py
first. If not, every doc and test name is ambiguous.

## 5.1 The shape, mapped from Blog's desk
| Blog desk | Training desk |
| --- | --- |
| 1 kind of post, 2 what you have, 3 sources and settings (B desk.js:48) | 1 Goal and audience (learner task, prior knowledge, time); 2 Materials and levels (101–401 chips, guide / brief kind / deck + delivery / practice / Yoodli); 3 Sources and settings (documents uploaded here, before Start; Your sites; public web; research questions; brand and look; copies; assistant). Then Start. |
| Progress: "Nothing needed from you…" | The same sentence, one clock for the whole start, and the current step in plain words (Researching, Planning level 101, Writing the 101 guide, Drawing the 101 deck). Each material opens on the desk as soon as it lands, so the desk opens before the deck is drawn. |
| One page of section cards | One desk per training with a tab per level (101 / 201 / …), plus a shared **Sources** panel (research is shared, R/pipeline.py:14-18). Inside a level, one column of cards: Plan (blueprint), Guide, Brief, Deck, Practice, Yoodli. |
| Outline tab | The level's **Plan** tab: modules, objectives and practice plan from the blueprint. Edits here are hub edits (5.5). |
| Finishing panel | Finishing for a training (5.7). |
| Top bar: Copy, Download, Google Doc, Mark as published | Download, Google Doc (send / bring changes in), **Mark this level ready**, Publish (team). |

## 5.2 What already exists that it reuses (ranked by value)
1. **Policy acceptance with no stop**: R/reviews.py:187-221 (`_policy_accept`, `_policy_outline`) and `workspace.accept_policy`, the brand's default look (`AUTOMATIC_LOOK`, R/pipeline.py), and C/review_policy.py + C/deck_flow.py `PAUSES`. Automatic draft already runs research → blueprint → guide → deck words → default look with no stop. A desk start is an Automatic draft whose final review is the desk.
2. **Edits that keep lineage**: `workspace.save(..., edit=True)` (S/workspace.py:554-560) records someone's edit, keeps `built_from` and snapshots history. Every desk save, rewrite, selection edit and restore can use it.
3. **Whole-file history**: `.training-studio/history/<artifact>/<sha>.md` (S/workspace.py:487-500), with event times in `session.events`. Per-section History can be derived by splitting those versions; nothing new is needed on disk for old trainings.
4. **Line diff and gate data**: S/desk.py:435-459 `changes` (difflib). Replace it with Blog's word diff for History (see section 6).
5. **In-process checks** that run in milliseconds after every desk change: S/checks.py `document_coverage` (278), `check_brief` (326), `lint_blueprint` (152), `check_scenario` (395), `check_yoodli` (492). These give each card its "Checked for you" line with no job.
6. **Worker jobs and briefs**: R/pipeline.py `document_work`/`brief_work` (1619-1666), R/briefs/*.md, R/agents.py confinement, R/worker_tools.py `submit_artifact` (checks a draft before it is kept), and retries and limits in C/stops.py.
7. **Pricing of a change**: R/reviews.py `rewritten` (124) and C/stops.py `redone` already say what a change rewrites downstream and what it last cost. These drive the "this also updates…" preview.
8. **Deck words per slide**: `deck/outline.json` slides carry `id`, `title`, `points`, `notes` and `serves` objectives (milestone-4 spec :262). The words gate already re-asks only changed slides (app.js:6643-6646, "Slides whose design was approved before and is unchanged are not asked about again"). Picture supply (R/page.py:705 `asset`), Redesign (695), and the look picker in C/deck_web/deck-panels.js are all in place.
9. **Requests at a gate** (`session.requests`, revise / rebuild with a note) and grouped requests in combined reviews. These are a whole-file version of a note, and remain the fallback for "Write the whole guide again".
10. **Copies**: R/copies.py, S/gdocs.py (hidden `covers` notes), and downloads (R/page.py:280).

## 5.3 What a note or edit calls, and how long it takes
Measured anchors: a whole no-deck training took 26 steps, ~14 min of agent time and $6.11
(T/docs/superpowers/specs/2026-10-13-milestone-3-rest-of-training.md:132). Research took ~5–6
min (milestone-2 :137-138). An 8-slide deck took ~10 min and $3.15, plus $2.31 for a repair
round (milestone-4 :17). The rate is 1.25 min and $0.40 a slide (R/deck.py:99). A Drive render
took 6–9 s (milestone-4 :21). The step limit defaults to 900 s (R/settings.py:101). Times
below for new jobs are estimates from those numbers.

| Desk action | Runner work | Estimated time |
| --- | --- | --- |
| Type in a guide/brief/scenario card | No job. Split/join the file, `workspace.save(edit=True)`, in-process checks, commit | <1 s |
| Guide section note → Rewrite | New job kind (e.g. `section`): the document brief plus Blog's surgical rule; inputs are that section, its `covers` IDs, the blueprint module those IDs belong to, only the findings it cites, and the neighbouring sections. The worker hands back the section. The runner splices it, keeps the `<!-- covers -->` line, re-runs `document_coverage` and citations, then saves. | 20–60 s |
| Guide section, no note → Write again | The same job from the module brief and earlier sections | 30–90 s |
| Brief section note | The same job with the brief's numbered heading fixed (`numbered_sections`, checks.py:314). Sections 1–8 cannot be added, removed or reordered, and "8. Sources" is rebuilt from the findings cited, never written by hand. | 20–60 s |
| Whole-document note | One job per section in order, with progress and Stop (Blog's `revise_all` chain), or today's whole revise request (one `document` step) | ~30–60 s per section; 1–3 min as one job |
| Selection: Rephrase / Shorten / Expand / Fix / Ask… | New `selection` job with the passage, its section and the cited findings. It must not drop a `[n]` citation; the splice re-runs the checks. | 10–40 s |
| Slide note (visible words) | (1) a scoped `deck-outline` revise for that slide (and its design, if designed); (2) `deck-start` re-split; (3) `deck-sections` for its section only; (4) `deck-whole` merge and render; (5) `deck-review` scoped to changed slides; (6) brand audit; (7) `deck-save`. **Today step 2 redraws every section.** `deck-start` is done only when `start.outline == said` (R/pipeline.py:1134-1143), and any outline change starts a new split. Unchanged sections need to be kept. | 3–6 min and ~$0.40–1.50, against ~10 min and ~$3+ for a full redraw of 8 slides |
| Slide note (speaker notes only) | Today a redraw, because `deck.kept` holds the notes to the outline. Needs a notes-only write into the saved deck with no redraw (new). | seconds (new) |
| Try another look | The existing `deck-look` step (one slide in each look), then the picker; Apply redraws the whole deck | samples ~1–2 min; apply ≈ a full deck |
| Scenario note | `scenario_work` with the note (whole file; scenarios are short). A person's own scenario is never rewritten, only laid out in their words (R/pipeline.py:30-32). | 20–60 s |
| Yoodli card note | `yoodli` job, then in-process `check_yoodli` limits | 20–60 s |
| Add a source | Not possible today: engine.py:3793 refuses once SETTLED. Needs a research update (harness-research synthesis with the new document, up to three author/check rounds), then the Sources panel marks findings as new or changed. | 5–10 min, more if rounds repeat |
| Plan (blueprint) edit | Typing is no job, but it cascades (5.5) | — |

One job per training at a time, as Blog does (B desk_jobs.py `_busy`). The engine's queue
already serialises a training's steps. Desk jobs must take `engine.files` and commit like
any step (R/engine.py:108-111).

## 5.4 What must stay
- **Levels**: per-level folders, every blueprint before the first guide, and "assume the reader can already" from earlier levels (R/pipeline.py:1600-1609 `_earlier`). Adding a level later becomes a new tab with **Add a level**.
- **Approval only by the person, on the page** (page approval mode; R/pipeline.py:52-55). Desk runs need no new approval path: "Mark ready" is the core's `approve` with the version the card showed (`seen`).
- **Readiness**: S/checks.py `readiness` (644) and `check`. The index is still written by the `package` step once every wanted file is approved, or left out.
- **Copies and the Google Docs round trip**: send, an explicit "Bring the Doc's changes in", the both-changed choice, and hidden `covers` notes. A pull lands as a version on the desk ("Before Google's text", as Blog does). Fix the pull trigger first (section 1, B1): today the button appears only after a failed push.
- **Downloads**, Word copies, the index.
- **Yoodli**: requires the brief and practice; the profile in assets/profiles/yoodli.json; fields laid out to copy; nothing posted.
- **Package / index / Publish** and the team rules: one computer drives a training; teammates read the desk with no notes or edits; Take over / Hand over; clash recovery; Share now or after each change. Blog shares desk work when you leave (B desk.js:455); do the same, or share on each applied change.
- **Deck rules**: the brand, harness-slides confinement, "a finding about what a slide says is never fixed for you", picture supply, and the grave-finding rule. On another computer the pictures stay local, so a teammate's deck cards show words only (docs/runner.md:347).
- **Research rules**: quotes verified word for word, unresolved findings never back a claim, gaps listed. These limit what a free-text edit may do: a desk check must flag a new claim with no `[n]`.

## 5.5 How a change reaches what was built from it
Lineage is whole-file sha256 (S/workspace.py:468-483, 374-397):
- blueprint ← intake, research
- guide ← blueprint
- brief ← blueprint, research
- deck ← blueprint + guide (research when there is no guide)
- scenario ← nothing
- Yoodli ← blueprint + brief + scenario + profile

Today the runner remakes anything out of date and puts it back to the person
(R/pipeline.py:31-35). On a desk that would turn every guide edit into a whole deck redraw
(~10 min, ~$3 for 8 slides). Proposed:
1. **Desk runs do not remake on their own.** A card built from an older input shows "Built from an earlier guide: 3 sections changed since", with **Update from the guide**, which previews what changes and its cost (reuse `reviews.rewritten` and `stops.redone`), or **Keep as it is** (the existing `accept` with a reason, S/workspace.py:834-847). This needs a matrix row.
2. **Scoped deck updates**: the changed guide sections' `covers` objectives become the slides whose `serves` name them. Only those slides are re-worded and redrawn (needs the kept-sections change in 5.3).
3. **Scenarios**: nothing reaches them today. Desk runs should compare the blueprint's practice plan entry a scenario came from and show "The plan for this practice changed". Fix the missing upstream (section 3 addendum) for new trainings only.
4. **Plan edits** fan out to the guide, brief, deck and Yoodli of that level. Show the list and the price before anything is written. Never auto-run.
5. **Research updates** (Add a source) fan out to every level. The same preview applies, per level.

## 5.6 What the stops, review levels, approvals and the matrix become
- **Review levels**: new trainings get one flow, the desk. Step by step, Balanced, Automatic draft and the combined reviews (review layout 1/2) stay for saved runs (`review_policy` / `review_layout` in run.json). The shared `review.level` keeps governing old runs and Presentation Studio. Training's form stops asking "Where this training stops". Its own Settings line goes, unless the owner wants a "check the research plan first" option.
- **Review stops** (research plan, research, blueprint, guide, brief, deck words, look, deck, scenario, Yoodli, first-drafts and finished-materials reviews): none for desk runs. Intermediates are accepted under policy (5.2 item 1), recorded as such, and never count as the person's approval of a material.
- **Problem stops stay** and move onto the progress screen or the card they concern: failed after three tries (Try again), out of time (Give it more time), out of money (Carry on), agent unusable (Check this computer), account limit (Wait, then Try again), a worker's question (a question card at the top of the desk), a picture needed (on the deck card, filled, with "Draw it without this picture"; section 1 B3), a deck sent back to its words (a banner on the affected slide cards), and grave review or audit findings ("Needs you before using" on the card; nothing is marked ready while one stands).
- **Approvals** become **Mark ready** per material and **Mark this level ready** (each its own core `approve` with `seen`). An edit after that drops the material back to draft, as the core already does.
- **Matrix rows to add**: desk start created; a policy-accepted intermediate (not a person's approval); a desk save and section rewrite (draft, inputs kept); selection edit; restore (as a version); out-of-date held (not remade on a desk run); Update from X (scoped); Keep as it is; Mark ready / level ready; Add a source → research update → materials out of date; slide note → scoped redraw; look change → full redraw; Google pull → version; old training opened on the desk. Also the missing rows from section 1 (Google pull/choose, picture supply, Redesign, looks not rendered).

## 5.7 Finishing tools (preview, then apply)
Blog's proposals model (B desk_finish.py) fits: each tool proposes, the person previews before and after, then Apply, Edit or Skip, with each Apply keeping a version.
- **In process, no job**: proofread, coverage gaps (an objective no section covers), a claim with no citation, scenario format, and Yoodli field limits.
- **Jobs**: Check against sources (per claim: supported, not in sources or contradicted; reuses the research record); Fit the learner's time (the guide and deck sized to `Time:`); Check the answer key (each answer says why, and why a plausible alternative is wrong; T plan 2026-10-20 "Instruction contracts"); Humanize (from Blog); Level check (nothing the earlier level taught is taught again; `_earlier`).

## 5.8 How saved trainings keep working
- A run with `review_policy` or `review_layout` keeps its gates and screens unchanged. New desk runs are marked in run.json (e.g. `flow: "desk"`, with the run schema bumped). The engine branches on it.
- A finished saved training offers **Open on the desk**, as Blog does (B desk.js:525 `sRunOnDesk`). Its files are already the desk's format: guide sections are `##`, brief sections are numbered, and history is under .training-studio/history. Approved stays approved until an edit.
- A conversation-made training (approval mode `chat`) is not on the desk until it is brought in ("Run this from here"). The conversation page (`training.py desk`) is unchanged.
- Training-level legacy (the question queue, pre-0.16 deck branches, words-only deck gates) is untouched (section 3).

---
# Section 6. What could be shared (core/studio_core and ui-kit, not copied)

Ranked by what is lost if each is copied a third time. This agrees with the Presentation

1. **The version store** from B desk.py:1005-1080 (`keep`, `versions`, `counts`, `restore`; a cap of 20, part-keyed jsonl) → `C/versions.py`. T: also add a reader that builds per-section history from the content-addressed `.training-studio/history/` files, so old trainings get History with nothing migrated.
2. **Split/join a Markdown document into parts** (B desk.py:66-210: `split`, `join`, fences, `##` sections) → `C/desk_doc.py`, with per-format hooks. T needs `<!-- covers: … -->` kept with its section, the brief's eight fixed numbered sections (no add/remove/reorder; Sources generated), and the guide's header block (For / Time / objectives) as the opening.
3. **The stale-form and job-basis rule**: `desk.checked`, per-part revisions and the job's `fingerprint`/`STALE` settle (B desk_jobs.py:74, 206). One rule for "the text changed while this was written".
4. **Surgical-edit and selection prompts**: `ACTIONS`, `WRITE_AGAIN`, `REVISE_ONE`, and the `_request` wrapper (B desk_jobs.py:40-62, 252) → `C/desk_prompts.py`. T adds the citation rule: keep every `[n]` and add no claim without a supported finding.
5. **Page kit served from C/deck_web** (already served to all three studios by C/server.py): word diff and History sheet (B desk.js:15-40, 502), the selection bar (479-516), progress sentence and clock (268-292), the Finishing panel shell (611-660), and the section card with note box. Blog's desk.js uses Blog globals (`studio`, `sNode`). Factor it into a small module that takes callbacks.
6. **Finishing proposals** (B desk_finish.py keep / read / apply / skip) → a core proposals module; each studio supplies `present` and `apply`.
7. **Step-time estimates** (B desk_jobs.py median of the last 20; `desk.estimate`) beside C/stops.py `took`/`cost`/`redone`, so every studio's "in about N minutes" is computed the same way.
8. **Desk CSS** (`.desk-*` in Blog's blog.css) → ui-kit/style.css. T: S/desk/style.css is a byte copy of ui-kit/style.css and S/desk/markdown.js of ui-kit/markdown.js, so re-sync both.
9. **T and Presentation: the deck pipeline itself.** The deck steps (R/pipeline.py deck survey, R/deck.py, R/slides.py, deck parts of R/engine.py) and the runner basics (agents, worker_tools, upkeep, gitstate, brand_source, team, companion, documents) are forked between Training and Presentation (section 3 addendum). A slide-card desk with scoped redraws and notes-only writes should be built once, in core, on top of what is already shared (C/deck_flow.py, deck_copy.py, deck_direction.py, critic.py, deck_web/deck-panels.js `lookPicker`), and then used by both studios.
10. **Already shared, keep it so**: C/research_contract.py, research_sites.py, research_view.py (Sources panel), review_policy.py (policy acceptance for desk starts), stops.py, model_profiles.py, studios_config.py.

Do not share the job queues. Blog's `tool_jobs` is a single worker. Training's engine runs
confined workers with worker tools and side-by-side sections. Share the settle and basis rule
instead.
