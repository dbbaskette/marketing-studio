# Presentation Studio workflow audit (main @ cc53056, 2026-10-26)

Read-only. Paths relative to repo root unless noted. P = studios/presentation, D = P/skills/presentation-studio/scripts/desk.


## 1. Broken or dead-end paths (ranked by what a person loses)

1. **Balanced skips the look pick for "Redesign, keep content".** core `deck_flow.HOSTS['presentation']['balanced']` makes `gate:outline` host the direction (deck_flow.py:61-62), but a Redesign deck has no `gate:outline` (P/runner/stages.py:105-108). So `review_policy.automatic` passes `gate:look` (checked: Balanced → classify/research-plan/research/look auto; outline/build stop), and `look.choose_default` (P/runner/steps/look.py:291-310) uses the default look with the receipt "Automatic draft: the brand's default look, {name}, was used." (deck_flow.py:85), under **Balanced**. README.md:3 promises "Balanced brings research, the outline and the brand's looks together for one review, where you pick the look". The form does say it, but only in one quiet line: "Balanced: it stops for the deck" (D/app.js:2906-2909). No test covers Balanced with Redesign (tests/test_flow_routes.py:186-187 is Step by step only).
2. **A PowerPoint delivery cannot be reached from any other computer.** The delivered file is `work/deck.pptx` (P/runner/steps/build.py:17; deliver.py:77-78), and `work/` is never shared. Teammates' Home and Decks still say "A .pptx, to download from its own screen." (D/app.js:1398), but their deck screen has no Download (`_rendered` is false, engine.py:3245-3250) and no **Send to Google Slides**. Publishing such a deck marks a revision with no deck in it.
3. **Undo is offered when it will be refused.** "Undo the last step" appears on every deck not working, delivered ones included (D/app.js:5720-5722). In a team workspace that shares after each decision the step is already shared, so the sheet opens and the runner refuses: "The last step cannot be undone: only the last thing done, when it was this deck's and is not shared yet, can be." (engine.py:260-261).
4. **"That's wrong" redraws at once and unpriced.** In the direction review, the document-reading line's "That’s wrong" sends the change on one click (D/app.js:4523-4524): the outline and looks are drawn again. Every other redraw says its cost first (`redo.says`, `research_price`, `leave_out_price`).
5. **"Sign in on Status" points to a screen with no sign-in.** The page says "Sign in on Status and Deliver to Google Slides afterwards." (D/app.js:5061-5062) and "Sign in to Google on Status to send this deck to Google Slides later." (5094-5095); P/runner/steps/existing.py:78 says "Sign in to Google on Status, under Check this computer". Status has only the printed `gcloud auth login` fix line (computer.py:156). The button it names is called **Send to Google Slides** (app.js:5088).
6. **Research described but not offered.** At the synthesis research stop (every new deck with a synthesis-capable Harness Research), the `gate.research` branch of `researchPanel` omits `addedPart` (D/app.js:4116-4134), so no question can be added. P/docs/runner.md:222 still says "add a question … Up to 10 questions can be added at once … A question added after the research is researched on its own", and README.md:32 says "Add up to eight optional questions on the form". Only the legacy queue shows "A question to add".
7. **A published revision cannot be read.** Published opens the deck as it stands now: "what opens is the deck as it stands now, not as it was published" (D/app.js:6926-6929). There is no way to see what was published.
8. **The original deck cannot be swapped.** At an existing deck's first stop the page says "To read another deck, stop this one and start a new deck from it." (D/app.js:5052-5053). The stopped deck then stays in every list until it is deleted.
9. **Delete is permanent.** "This cannot be undone from this page. Its history stays in git, where someone who knows git can bring it back." (D/app.js:204-205). Blog Studio keeps 30 days under Recently deleted, with Restore (studios/blog/.../runner.js:1064).

## 2. Confusing or contradictory copy; two names for one thing (ranked)

**Copy that is true only at Step by step (new runs default to Balanced, core review_policy.py:32-33):**
- Route card and document step: "you confirm whether it is a finished script for the slides or material to build from" (D/app.js:116-118, 2838-2840). Under Balanced and Automatic the reading is not asked about (it is one line inside the direction review).
- Research chip: "You approve the research plan, then the findings, before the outline is drafted." (D/app.js:3129-3132).
- Start step: "From the first decision on, you see the slides themselves." (D/app.js:3185-3186). At Step by step with research, the first decisions are the plan and the findings; at Automatic the first decision is the deck. Set-up says "At every decision after the first, you see the slides themselves" (2514).
- Home: "stops each time it needs your decision" (D/app.js:1437-1439). README.md:29 "The page stops at each of these and waits for you"; README.md:99 "Decide at each stop"; P/docs/runner.md:294 "A deck moves past a stop only by your decision on the page."
- **Every step** says "Your decision" for every gate (D/app.js:3700), including gates the engine relabels "Continue the … automatically" (engine.py:2757-2759). One row then reads "Continue the outline automatically · Your decision".
- Under Balanced the default-look receipt starts "Automatic draft:" (deck_flow.py:85), naming the wrong level (§1.1).
- Balanced moves "Review the direction" after the looks are drawn (stages.py:117-124), but the beads group by stage (D/app.js:3644-3658). While the looks are drawn, **Outline** says "Still to come" and **Look** says "Now"; at the direction stop, **Look** says "Still to come" though its samples are on screen.

**Two (or more) names for one thing:**
- **Assistant / agent / worker / AI.** README and the research copy say "assistant" ("your assistant’s own web search tool", D/app.js:3104). Set-up says "The agent that does the drafting … An agent is the AI that drafts" (2555-2557); "Drafted by"; "No agent was found". The deck says "A worker asks:" (3839), "it goes to the worker that draws this slide again" (3468-3469), and has a "Working now" card of workers.
- **Revision**, three counters:
  - deliveries (deliver.py:16-17, 67), "Revision 3" on the deck;
  - published tags (team.py:36, 306-308), "Published as revision 1" on the same screen (D/app.js:5073 vs 5963);
  - the preview attempt: "Applies to this displayed revision." (4849).
- **Deliver to Google Slides / Send to Google Slides.** README.md:129 and runner.md:228 say "Deliver to Google Slides"; the button is "Send to Google Slides" (D/app.js:5088); the deck-stop note says "Deliver to Google Slides afterwards" (5062).
- **Review / check.** The step "Check the deck" (stages.py:62) is the review. The page says "The review has nothing left to raise" (D/app.js:4958), "First draft, not checked", "See the first draft before the deck is checked" (3174), "Check the deck" (4924); "review" is also the Review level, "Review the direction" and Home's "Review <title>".
- **Brand check / brand audit.** "The brand’s own check" (D/app.js:4809); a kept gate says "Audit blocker: …" (core review_policy.py:101); README.md:35 "notes from the brand check".
- **Asking for a change** has about a dozen names, by stop:
  - Sheet: "Ask for changes".
  - Deck slide: "Ask for changes to this slide" and "Change what it says" (3458-3472).
  - While building: "Send slide feedback" (4845), shown later as "Your feedback on it" and "Saved slide feedback".
  - Next-step note: "Note for the next step" (3577).
  - Outline row: "Ask for changes" / "Keep it as it is".
  - Research: "Ask about this finding" / "Keep this finding" / "Research again" / "Don’t research it again" (4239-4248).
  - Direction review: "Request changes to the research" / "Research again" (4574-4578).
- **"Ask about this finding"** sounds like a question about one finding. It opens "What is wrong with “X”?" (4219-4220) and reruns the whole research (runner.md:344). **"Keep this finding"** undoes it but reads like the opposite of **Leave out**.
- **Workspace / work folder / where your decks are kept / folder.** Settings' Shared settings card says "Your assistant, work folder, brand and delivery choices apply across all studios." (D/app.js:1730); the Workspace card and Set-up say "Workspace: where your decks are kept" (2353).
- **Three ways into the same values.** Settings has "Change shared settings" (to /onboarding/, 1731), "Change the set-up" (1886) and "Change them" (1723), and Set-up writes the same shared values again ("Your team’s repository, when to share, your name, the agent, the brand and the output are shared by every studio", 2488-2490). The review level is shared but changed on Settings' own card (2937-2957).

**Other wording:**
- **"We"/"us" voice**, unlike the rest of the page: "What you gave us" (D/app.js:3982), "Confirm what you gave us" (stages.py:30), "Approve, and it carries on from what you gave us" (5028), "We may tighten…", "Tell us which slides and what to fix." (129-130).
- **Success shown in the alert banner.** `notify()` (the red `.notice`, role=alert) carries "Deck copied into this workspace." (1574) and "Slide feedback saved." (4861).
- **Jargon:**
  - "Visual storyboard: proposed wording and structure, before native slide construction. This preview does not approve the outline or choose final slide layouts." (4645-4646)
  - "Copy a deck made through the conversation workflow…" (1562)
  - "Applies to this displayed revision. Other sections keep working." (4849)
- **Warning bead on normal progress.** "Unreviewed" during a normal build uses the `late` (warning) bead (4828).
- **Research plan count.** It always says "searched on the web" (4039-4040), even for research from your documents or sites only.
- **Rehearsal.** README.md:38 says "Rehearsal is not part of a deck yet, so the page does not show it". Yet every deck carries "Rehearse (coming later)" (stages.py:72), and deck.css:25 says "Rehearsing with Yoodli is shown dimmed", naming a third-party product for a style nothing uses (§3).
- **Old brand step.** The look gate still has the cover path: "This is your cover, drawn in that brand, so you can see it is the one you meant." (4729-4731). The rebrand sheet comment says "The cover is drawn again" (5535-5536), while its own text says the looks are drawn again (5565).

## 4. Layout-rule gaps, screen by screen (rules: docs/design/golden-gate.md:51-67)

What is already right: glass only on the sidebar, toolbar and sheet (cards are opaque `.card`; `.shine` is disabled in ui-kit/style.css:327-330); shared controls come from ui-kit; controls are at least 2.75rem tall. Screens are ranked by use.

1. **Deck, working or at a stop** (D/app.js:5726-5785, deckActions 5679-5724).
   - **Toolbar.** Now: Approve (filled), **Ask for changes** (a plain, unquiet button), Pause (plain), Stop (quiet), Resume, "Undo the last step" (quiet, long name). Rule: one filled, the rest quiet. A long screen-specific action ("Undo the last step") goes under the lede.
   - **Lede.** Now: the now-line and the state bead come before `.lede`, and three more sentences follow it (3541-3555). Rule: one sentence in `.lede` first.
   - **Order.** Now: the intro, then "Note for the next step", then the "Where it is" timeline, then team notices, then the problem, then the worker's question, then the gate. Below them come Delivered, then "Slides taking shape", then workers, Publish, cost, every step, saved details, troubleshooting, "Who runs this deck" (Hand over) and Delete. Rule: what needs the person first (problem, question, gate), then work in progress (slides taking shape, workers, note box), then finished and archived work (Delivered, Publish, Delete).
   - **Headings.**
     - Now: the direction review nests cards inside a card. The "Review the direction" card holds the "What the research found" card and the "Choose the look" card (4555-4566).
     - Panels add `h3` and `h4` sub-headings ("Your questions", one `h4` per question, "What the independent check said", "The brand’s own check", "Every revision").
     - The research form inside the direction review is a bare textarea with only an aria-label and no Cancel (4570-4578).
     - Rule: one heading level per card, with sections as sibling cards.
   - **Phone.** Now: `foldActions` puts every action but the filled one into a "More" menu (627-640). The submit for an item-by-item stop lives only in the toolbar ("The one button that sends the marks is the toolbar's", 5452-5453), far above the review bar the tally sits in. Rule: toolbar actions wrap under the title, and fixed bars sit above the tab bar.
   - **Spacing.** Now: deck.css uses 0.35/0.55/0.6/0.7/0.8/0.9rem (deck.css:11-124). Rule: 1.1rem between cards and sections, 0.6rem inside a group.
2. **New deck** (D/app.js:2710-3230).
   - **Form.** Now: a full-page wizard. The route cards come first, then two or three pages titled "What it is about", "How it looks, and starting it", with "Step 1 of 3" as small text above the title. The foot has "Back a step" or "Another way to begin" with Continue or "Start the deck"; there is no Cancel. Rule: a sheet in numbered steps (`1. …`, `2. …`, `3. …`) split by hairlines, ending with its submit and Cancel together. Blog's create sheet does this (`sCreateStep`, studios/blog/.../runner.js:641).
   - **Lede.** Now: the step pages have none; the route step's lede is a question ("How does this deck begin?").
   - **Order.** Now: the last step puts the brand first, then a closed "Options" disclosure (output, assistant, first draft), then "Where this deck stops", then an aside. The deck's review level, which changes what the person will be asked, sits under a collapsed disclosure's sibling, after optional settings.
3. **Home** (D/app.js:1470-1494).
   - **Toolbar.** Now: `actions: [start, lead]` puts the quiet "New deck" before the filled "Review <title>". Rule: primary first, then quiet secondaries.
   - **Lede.** Now: none; there is a `.large-title` greeting in the page instead.
   - **Order.** Now: the Updates card (setup) comes before "Needs you". Rule: what needs the person first, then work in progress, then ways to start, then setup, then finished.
   - **Lists.** Now: deck rows (`ul.rows` inside cards) of objects a person opens. Rule: objects a person opens are cards.
4. **Decks** (D/app.js:1523-1545).
   - **Lede.** Now: none.
   - **Filters.** Now: one search box, applied as each key is typed, with no choice filters and no Search button. Rule: search first and widest, then choice filters such as where it stands, how it began and who runs it, then a plain Search button; on a phone only search, with a Filters button.
   - **Selection.** Now: nothing; Delete is one card at a time. Rule: "Select all on this page", and a `.glass` selection bar while something is ticked, with Delete the main action. Blog does this (#94).
5. **Settings** (D/app.js:1727-1744).
   - **Toolbar.** Now: no primary.
   - **Lede.** Now: none.
   - **Content.** Now: ten cards. Three of them lead to the same values (Shared settings to /onboarding/, Workspace's "Change the set-up", and "What a new deck starts with" → "Change them"). Two of them, "Where new work stops" and "Brand skill", write shared values in place. Rule: one sentence lede, then one clear place per value.
6. **Set-up** (D/app.js:2540-2567). It has a lede and Save at the foot (good). "Save" sits at the end of a very long form that mixes shared and studio-only values. Shared values duplicate Shared settings (/onboarding/), so this screen should hold only the studio-only values: previews, limits and the brand skill choice.
7. **Status** (D/app.js:1665-1681).
   - **Lede.** Now: none.
   - **Order.** Now: the filled primary is "Check this computer", but its result card ("This computer") is last, below Versions and skills. Rule: show the result of the primary near the top, or say where it appears.
8. **Published** (D/app.js:6936-6954). It has a `.lede` (good). The deck rows sit in a card ("Published decks") as `ul.rows`. Rule: cards for objects, or a quiet `.table` with one Open per row (revision, when, by whom, delivered or not) that becomes a card per row on a phone.
9. **Sheets.**
   - "Bring in a deck" (D/app.js:1558-1581) is a list of action buttons with Cancel and no submit. Its success goes to the alert banner.
   - The picture form inside an outline row (4469-4478) and "Request changes to the research" have no Cancel next to the submit.
   - Ask for changes, Choose another brand, Undo, Take/Hand over/Publish, Delete and Upgrade follow the rule (submit and Cancel together; Delete and Upgrade use `.sheet-part`).

## 3. Cleanup

### 3a. Dead code and unused routes or functions
- **Routes:** none dead. Every READS/WRITES route in P/runner/page.py:111-120 is called by D/app.js; `/api/deck-draft` is the storyboard frame and `/api/progress-seen` is called at app.js:905.
- **Safe to delete now:**
  - D/app.js:3138-3152 `asksFor()`, which nothing calls. It also lists every stop as if Step by step, a near-copy of `stopsFor` at 2886.
  - D/app.js:3685-3686, the `found.at === 'later'` branch. `stagesOf` never yields `'later'`.
  - deck.css:25-32 `.timeline .bead-stage[data-state="later"]` and `.bead-later`, with the comment that names Yoodli. They are unused, which corrects the parallel pass's "no unused CSS".
  - D/app.js:2873 `firstDraftChoice()` and 2977 `siteShown()`, trivial wrappers.
  - The duplicate section comment at app.js:6912-6914.
  - P/runner/worker_tools.py:497 `as_kept()`, which nothing calls.
- **Callers only in tests:** P/runner/brand.py:422 `look_status()` and P/runner/steps/build.py:527 `guided()`. Drop them with their tests, or use them.
- **The `rehearse` step:**
  - It sits in stages.py:72-73, 94, 170, 213-219; engine.py:175, 186, 3141; core review_policy.py:124-125; app.js:3643, 3723.
  - Every deck carries it and nothing runs it.
  - Saved run.json files hold `gates.rehearse`, so the readers (survey, timeline, gate lookups) must first ignore an unknown gate key; it is not a one-line delete.
- **Code naming:** `window.TrainingStudioMarkdown` (app.js:3964) names another product in the Presentation page; rename it in ui-kit/markdown.js together with Blog and Training.

### 3b. Legacy paths kept for old runs (safe now vs needed for saved decks)
1. **The research question queue, used when run.json has no `research_contract`.**
   - Code: research_steps.py:80-95, 343-493, 596, 632 (30 questions); research.py:122-148; the briefs research-plan-queue.md and research-question.md; tests/stand_ins/research.py; test_runner_research.py:209-555.
   - **New decks can still land in it.** `research_contract.snapshot()` returns None for a Harness Research without synthesis, or on any read error (core research_contract.py:129-134, engine.py:773-778). Nothing at start refuses that; the person silently gets the old 30-question queue, and the legacy research page.
   - To retire it: first make start refuse with a sentence when synthesis is not found, then remove it once no unfinished run lacks `research_contract`.
2. **The cover sample for a brand skill without looks.** look.py:59-122, 329; engine.py:1492-1503, 3013; app.js:4721-4735, 5535-5541.
   - Nearly unreachable: a brand skill older than 0.14.0 stops the deck (engine.py:1391-1395, brand.py:88-90).
   - It can still be reached by a versionless skill, or by a saved deck whose `brand/` contract came from a pre-0.14 skill (the floor is skipped when the contract exists, engine.py:1392).
   - Can go with a release note. Tests: test_step_look.py:59-72, 156-179; test_desk.py:1633, 1738.
3. **Keep for saved decks:**
   - a missing `review_policy` read as Step by step (core review_policy.py:71-74);
   - `research_sources` read as `research_from` (decks.py:94-130, core research_sites.py:220-228, shared with Blog);
   - `LEGACY_JOBS` cost lines (jobs.py:84-88);
   - the older outline-with-pictures shape (build.py:1234);
   - `critic.LEGACY` questions for rounds saved before questions were kept (build.py:76, 396, 1577, 1662). These only matter mid-build on the computer that built the deck.
4. **Migrations of this computer's own settings, not of saved decks:** settings.py:26, 483; gitstate.py:178-184; worker_tools.py:1577. Drop after a release or two.

### 3c. Helpers duplicated from core/studio_core, or forked between studios (ranked by drift a person feels)
1. **P/runner and studios/training/runner are hand-kept forks.** Lines that differ, of file length:
   - brand_source.py 2/364 (only the product name)
   - companion.py 7/250
   - research.py 23/148
   - agents.py 40/755
   - brand.py 45/443
   - team.py 70/377
   - gitstate.py 119/796
   - documents.py 130/647

   They have already drifted: `agents.data_shared()` (P/runner/agents.py:167-184) exists only in Presentation Studio. They can move to core with a product parameter, the `for_product` pattern scripts/server.py and studios_config.py already use. `scripts/studio_core` is a symlink to core, so each studio stays independently runnable. Revisit P/AGENTS.md:10 and vendor.json, the vendoring rule that keeps them forked.
2. **Partly shared structure:** settings.py, setup.py, slides.py, upkeep.py, worker_tools.py, page.py. Share the common parts, such as the companion pin checks, setup checks and limits.
3. **Scripts:** computer.py (10 lines differ) and sync_guidance.py (68) are near-copies of Training Studio's.
4. **Inside one studio:** app.js `stopsFor` (2886-2910) recomputes the review-level rule that core `review_policy.ahead` already gives the server (engine.py `_still_to_come`). The start form should ask the runner instead; this is how §1.1 went unnoticed. The level labels are duplicated three times: `REVIEW_WORDS` (624), the inline map in `costCard` (5229) and core `LABELS`.

### 3d. Stale docs and README lines (ranked by what a reader gets wrong)
1. README.md:29 "The page stops at each of these and waits for you." This holds only at Step by step, and README.md:31-36 lists the Step-by-step stops as everyone's. README.md:3 says the look is picked under Balanced, which is false for Redesign (§1.1).
2. docs/runner.md:61 "**The brand.** Before any slide is designed, the runner draws the deck's cover…" describes the pre-looks brand step.
3. README.md:34 "A brand skill too old to offer looks shows your cover in the brand instead." and runner.md:190 "a new deck waits at its brand step" contradict each other, and the code refuses such a skill.
4. runner.md:222 lists adding questions at the research stop, which synthesis research no longer offers (§1.6).
5. README.md:129 and runner.md:63 say "Deliver to Google Slides"; the page says "Send to Google Slides" (app.js:5088).
6. runner.md:125 says "the page does not offer this yet"; it does: "Bring in a deck" (app.js:1541).
7. README.md:151-164 sit after "## Licence" (:147) and repeat earlier lines. README.md:160-162 points at "the live-preview issue", which is #15 and closed, while the page already takes feedback during the build. runner.md :135, :184 and :221-227 sit after "What the runner guarantees" and repeat :53 and :63.
8. README and runner.md leave out "See the first draft before the deck is checked" (app.js:3174) and "Delivered: first draft, not checked" (5071). They also leave out that PowerPoint deliveries stay on the computer that made them (§1.2).
9. capabilities.md:17 calls the looks picker "cover preview"; capabilities.md:37-38 says rehearsal "is labeled as future work".
10. Skill references:
    - references/workspace.md:17 "shown on its cover"; :31 "`schema` 1" (the runner writes 2 or 3); :34 "`gate:look` (the brand)".
    - references/workspace.md has no `review_policy` key, so a deck made in a conversation and brought in is read as Step by step.
    - references/levels.md:9-10 and routes.md:7, 23 say "Brand" where the stop is the Look.
11. docs/development.md:
    - :3 and vendor.json:3 point at the retired dbbaskette/training-studio repository.
    - :84 says "A release is a `vX.Y.Z` tag on `main`", but tags are `presentation-studio/vX` (check upkeep.py:145).
    - :89 uses harness-slides v0.14.2 as its example; the pin is 0.16.0.
12. specs/2026-10-14-presentation-studio-design.md:47, 64, 96, 130, 248 describe the rehearsal placeholder and the cover-only brand step, yet README.md:145 calls it "the full specification". Mark it superseded. docs/acceptance.md:98-163 is a 0.1.0 hand-test record; date it.

### 3e. Tests for removed or vestigial behaviour
- **The `rehearse` step:** test_stages.py:19-51 and :100, test_flow_routes.py:30, test_engine.py:31 and :184. Change them with the reader change in 3a. Keep test_page_app.py:184, the no-placeholder guard.
- **The cover sample:** test_desk.py:1633 and :1738, test_step_look.py:59-72 and :156-179.
- **The question queue:** test_runner_research.py:209-555 and stand_ins/research.py. Keep them until the queue is retired.
- **Sole callers:** the tests that are the only callers of `look_status` and `guided`.
- **Missing coverage:** no test walks a route under Balanced or Automatic end to end (test_flow_routes.py walks Step by step only). Add Balanced and Automatic walks for every route and level; Redesign under Balanced would have caught §1.1.
- The suite was not run: this computer has only Python 3.9.6, and the suite needs 3.11 or newer.

### 3f. Safe now / needs a guard / keep
- **Safe now:** the dead JS, CSS and Python in 3a; the doc fixes in 3d; moving the near-identical runner modules into core.
- **After a start guard:** the question queue.
- **After the reader change:** `rehearse`.
- **Keep for saved decks:** the items in 3b.3.
- **Drop after a release:** the migrations in 3b.4.
- **With a release note:** the cover sample.

Paths: P = studios/presentation, B = studios/blog/skills/blog-studio, C = core/studio_core.

## 5. A deck desk, in depth

### 5.0 Blog's desk, the model being copied (what matters for decks)
- After Start there are no stops. Steps run as one chain (`desk/start.json` `steps`/`step`, B/scripts/desk.py:428-527; `desk_jobs.begin/_advance` 1152,1243). The time estimate is the median of this computer's last 20 runs of each step, falling back to fixed minutes (desk.py:389 `MINUTES`; desk_jobs.py:1195-1290).
- The desk record is `desk/draft.json` plus `desk/versions/<part>.jsonl`. It keeps the last 20 versions of each part, merges one editing session into one version, and skips torn lines (desk.py:1005-1080).
- Stale checks are per part. A form that saw revision `seen` may still change a part nothing else has changed since (desk.py:666-681).
- Each job carries the part and that part's text fingerprint (`basis`). The result lands only while the text is unchanged, and the old text is kept as a version first (desk_jobs.py:1431-1520, `STALE`).
- One job per blog (desk_jobs.py:201 `_busy`). Kinds: `desk-section` for a note or Write again (292), `desk-selection` (346), `desk-revise-all` chained one section at a time with Stop (445-503), and the finishing kinds.
- Finishing results are proposals kept beside the draft. Apply or Skip works per item (desk_finish.py:42-300). Proofread runs in process, with no job (509).
- Old runs: gated blogs stay as they are. A finished one offers **Open on the desk**, which builds a desk draft from DRAFT.md and leaves the run readable (desk.py:556-594; runner.js:433,1046). `record['flow']='desk'` marks new desk blogs (desk.py:477).

### 5.1 What already exists in Presentation Studio that a deck desk reuses (ranked by value)
1. **A per-slide note that redraws only that slide's section, keeping the section's other slides exactly.**
   - At the deck stop, `slide_notes` and `slides` go to `_ask_again`. It sends back only the sections that hold the named slides (P/runner/engine.py:2179, `_sections_for` 1831).
   - `section_work` names the focused slides, freezes the others as `unchanged_slides`, and says "Copy all other slides in your section exactly" (P/runner/steps/build.py:1237-1253). `kept` enforces it (build.py:348).
   - This is the desk's slide note, already working. Today it is gated behind **Ask for changes** at the deck stop.
2. **Notes while the build runs.** `build_feedback` (engine.py:1721) invalidates one section's live preview and redraws it with the note. A note that arrives after its section is drawn is kept as that slide's mark for the deck stop (`_keep_feedback` 1761). Page: `progressFeedback`, "Send slide feedback" (D/app.js:4840). On the desk this becomes the slide-card note during progress.
3. **Section reuse after an outline edit.** `build.start` keeps every section whose slides say the same in every field the composer reads (`_kept`, build.py:1079; `DRAWN_FROM` 1071). "Change what it says" reopens the outline with the slides marked, then redraws only the changed sections (`_say_again`, engine.py:2069). This is the Outline tab's engine.
4. **Live previews.** `build_progress` (P/runner/build_progress.py) publishes unreviewed per-slide pictures for each section attempt. The page shows them as "Slides taking shape" (app.js:4826). This is the progress screen's body.
5. **Repair rounds with no person.**
   - The preview screen sends back slides with errors or overlaps (`preview_repairs`, build.py:1379).
   - Brand audit blockers send their sections back (`audit_round` 1628).
   - The critic's major or critical findings send their sections back. All of this is capped at `REPAIRS = 2` (build.py:97).
   - All of it already runs without a stop. Keep it in progress.
6. **The deferred critic.**
   - `initial_review: 'user-first'` builds and renders but skips review and repair (`decks.user_first`, P/runner/decks.py:43; `_build_review` engine.py:1679).
   - `review_draft` asks for the check later, bound to the deck hash on screen (engine.py:1787). Page: "Check the deck" (app.js:4927).
   - This is the Finishing tool **Review the deck**, already built.
7. **Review reuse.** `reusable_review` keeps verified evidence for slides that did not change. The reviewer re-inspects only changed slides (build.py:1692, 1742). A desk review after a one-slide redraw is therefore cheap.
8. **Text patches for existing decks.**
   - `patch_work` is the assistant's plan of text, runs, alt and title changes per named slide, each with its expected hash (P/runner/steps/existing.py:484, `FIELDS` 80).
   - `apply_patch` runs harness-slides `pptx patch` then `pptx compare` against an allow list (570-610; P/runner/slides.py:786-806).
   - `pairs` gives before and after pictures (627).
   - This is the selection edit for `route == 'existing'` decks, and the only safe text edit for Brand only and Polish, whose words must stay verbatim.
9. **Costs said before a redraw.** `_redo` gives the seconds and dollars of each step's last try (engine.py:3135). `_last_build` gives the whole build (3215). The page says it with `wholeDeckSays` (app.js:3417).
10. **Look choice.**
    - Look samples: `look.draw_looks` (P/runner/steps/look.py:127).
    - Choosing: `choose`, `choose_default`, and the honest "unreviewed draft of its look" path (212, 292; C/deck_flow.py `UNREVIEWED`).
    - Picker UI: `lookPicker` in C/deck_web/deck-panels.js, already shared with Training Studio.
11. **Delivery and revisions.** `deliver.again` sets deliver.json aside and keeps revisions (P/runner/steps/deliver.py:98). `deliver_again` sends PowerPoint to Google Slides without a rebuild (engine.py:3437).
12. **Outline word check and storyboard.**
    - `outline.apply_edits` re-checks with `outline check` (P/runner/steps/outline.py:449).
    - `storyboard` renders the outline's words as HTML with `outline draft` (engine.py:2857; slides.py:832).
    - These become the Outline tab.

### 5.2 Where the desk needs new code (ranked by what a person loses without it)
1. **A slide note outside a stop.**
   - Today a note needs `gate:build` waiting, or a delivered deck (engine.py:1925-1927 `NOT_WAITING`; `after`).
   - Every request reopens `gate:build` through `stages.reopen`, then re-runs whole → review → repair → render, and the deck stops again.
   - Needed: a desk action that sets `state['asked']` for one section and re-runs build-sections:<that section> → build-whole → build-render, with no gate. Review is skipped, as with `user_first`.
2. **Selection edits on slide text (composed decks).**
   - Nothing exists for scratch or document decks. Slide words live in outline.json, and `kept` holds the drawn text to them.
   - Proposed chain:
     - A Blog-style `selection` job rewrites one field of one slide (title, subtitle, a point, caveat or notes).
     - `outline check`.
     - Patch the same text into the drawn section JSON and run `compose compile` for that section. If it fits, no composer job is needed.
     - Merge, compile and preview the whole deck, then the brand audit.
     - Fall back to a focused section redraw when compile refuses (text does not fit).
   - Never edit a .pptx by hand: "The studio never edits a slide file itself" (P/docs/runner.md:131).
3. **History per slide.** Nothing keeps a slide's earlier text or drawing. Rounds are replaced (`draw_whole` deletes older `whole-*`, build.py:1505). Needed, per slide:
   - The outline slide JSON, the composition slide JSON and the picture.
   - Text in `desk/versions/<slide-id>.jsonl` (shared). Pictures and composition in `work/desk/` (never shared, like `work/`).
   - Restore puts both back and recompiles, with no assistant.
   - Compare shows before and after pictures plus the word diff.
4. **Speaker notes as their own edit.** `notes` is in `DRAWN_FROM` (build.py:1071), so a notes-only edit redraws the whole section through an assistant. Notes are not in the pptx inventory, so `pptx patch` cannot reach them (outline.py:24-25). Needed: a notes edit that skips the composer: outline, then the composition's notes, then compile.
5. **The whole-deck note.** Today a deck-stop note with no slides marked redraws every section at once (`AT_ONCE = 3`, engine.py:153; `_sections_for` 1831-1844). Blog revises section by section with Stop, and a failure leaves the others done (desk_jobs.py:445). Keep the deck's parallel redraw (it is cheaper per wall-clock), but add Stop and "N of M sections".
6. **Add a source after start.** Research is one heavy run with check rounds ("48 minutes and $9.80", docs/superpowers/specs/2026-10-22-phase-3-research-stop-design.md:168). Add a source must attach the file for later slide notes and the fact check, and must not rerun research unless asked. If asked, price it as the research stop does now.
7. **Rehearsal.** The `rehearse` step is "Rehearse (coming later)" and never runs (P/runner/stages.py:72, 170; README.md:38).

### 5.3 Which runner steps and Harness Slides commands each desk action calls, and how long each takes
The repo records no measured duration for a section draw, a render or an audit.
- What is recorded: per deck, `steps[<name>].tries[].seconds` and `dollars`, which `_redo` already says. Also the per-step limit `step_seconds = 900` by default (P/runner/settings.py:109, range 60–7200 at 77).
- Known bounds:
  - A composer may render its section up to `PREVIEWS = 4` times (build.py:96).
  - LibreOffice renders one at a time. Drive previews run up to `HARNESS_PREVIEW_POOL_SIZE` (4) in parallel (runner.md "Previews").
  - Training Studio's milestone-0 live jobs took 6–94 s each (studios/training/docs/superpowers/plans/2026-10-13-studio-runner-milestone-0.md:89-115).
  - Training's fixed whole-deck estimate is "about $7.20 and 40 minutes of agent time" (docs/superpowers/specs/2026-10-22-phase-2-honest-copy-design.md:277).
- So a deck desk cannot promise Blog's "seconds to under a minute" for a slide note. A section job is minutes-scale. The desk must say the last recorded time, as `_redo` does, or keep a per-computer median per action (Blog's `expected_minutes`).

| Desk action | Runner steps | Harness Slides / brand commands | Assistant? | Time evidence |
| --- | --- | --- | --- | --- |
| Slide note (composed deck) | build-sections:section-N (`section_work` focused) → build-whole (`draw_whole`, `audit_round`) → build-render | `compose compile` (repeated by composer via check_section), `compose preview` ≤4 by composer; then `compose merge`, `compose compile`, `compose preview` of the whole deck; brand `presentation --file … --json` audit (brand.py:360); `compose render`/copy | Yes, one composer | Unknown; bounded by 900 s step limit; last try said by `_redo` |
| Slide note, later reviewed | + build-review (only changed slides inspected) → build-repair ≤2 rounds | `compose critique` | Yes, reviewer (+ composers on repair) | Unknown; per-run tries recorded |
| Selection edit (composed deck), fits | new desk-selection job → `outline check` → section compile → whole merge/compile/preview → audit | `outline check`, `compose compile`, `compose merge`, `compose preview` | One small text job | Text job likely like Training's 6–94 s jobs; render unknown |
| Selection edit, does not fit | as above, then focused section redraw | as slide note | Yes | as slide note |
| Selection or slide note, existing deck at Selected changes / Brand only / Polish | patch (`patch_work`) → `apply_patch` → pictures (`_patched_pictures`, build.py:1883) | `pptx inspect`, `pptx patch`, `pptx compare`, `compose preview`/pictures_of | One small plan job | Unknown; no composer, no section render |
| Speaker notes edit | outline + composition notes → compile → whole preview | `compose compile`, `compose preview` (or skip preview: notes are not drawn) | No | Code only |
| Restore a slide version | composition slide put back → whole merge/compile/preview → audit | `compose merge`, `compose compile`, `compose preview`, brand audit | No | Code only |
| Outline tab save | `apply_edits` → build-start (`_kept`) → changed sections only → whole → render | `outline check`, `outline start`, then as slide note per changed section | Yes, per changed section | `_last_build` prices a whole redraw |
| Change the look | look-preview again → `look choose` → every section | `look samples`, `look choose`, then full build | Yes, all sections | `_last_build` |

### 5.4 The desk, screen by screen (deck version)
- **Start, in three steps, like Blog's `DESK_START_STEPS`.**
  1. **Kind of deck.** The three routes as cards: an idea, a document, an existing deck. For an existing deck, the five levels sit here.
  2. **Sources and settings.**
     - Documents and links, plus research from your documents, your sites and/or the public web (already shared: `research_sites.effective`).
     - Minutes, audience, brand and variant, output.
     - **Look**: "Pick it when the samples are drawn" (default) or "Use the brand's default look".
  3. **What you have.** Title and goal, the brief (scratch), the document (with an optional "it lays out the slides / it is material" override in place of the classify stop), or the deck.
  - Then **Start**. No review-level card.
- **Progress, with no stops.**
  - First line: "Nothing needed from you…". The current step in words comes from `Step.doing` (stages.py:22-72), with one clock.
  - "Slides taking shape" shows below, with per-slide notes (reused).
  - The single exception: the look. When the person chose to pick it, the samples card appears in progress as the one thing that needs them. That is a pause, not a gate (see 5.6).
- **The desk.** One card per slide, grouped under section headings, which match harness-slides `outline start` sections. Each card shows:
  - The rendered picture.
  - The slide text, editable: title, subtitle, points, caveat, source.
  - The speaker notes.
  - The brand-check and review findings for that slide (today in `buildPanel`, app.js:4916-5060).
  - "How should this slide change?" with **Redraw**, and History.
  - Existing decks show the before and after pair (`pairs`).
  - A top box takes the whole-deck note.
  - Tabs: **Slides** | **Outline** (the reordering and per-slide edits from `outlinePanel` app.js:4555, with the storyboard).
- **Add a source:** an aside, as in Blog.
- **Toolbar:** **Deliver** (filled), then Download, Finishing.
- **Finishing, preview then apply.**
  - **Brand check:** in process, with no assistant. It shows the last `audit_round` result per slide. Apply redraws the slides with blockers.
  - **Review the deck:** `review_draft` / `review_work`. Proposals are its findings per slide. Apply sends those sections to repair. Skip keeps them as notes.
  - **Speaker notes:** a job that proposes notes per slide from the outline and sources. Apply writes the notes with no redraw.
  - **Rehearse:** in process. Notes word count against the form's minutes (≈150 wpm) per slide and in total, with slides that run long. Optional job: "likely audience questions". This replaces the dead `rehearse` step.

### 5.5 What must stay
- **The look choice.** The brand defines it as a checkpoint (C/deck_flow.py:27-31, `CHECKPOINTS`). `look choose --outline <approved>` needs the outline the samples were drawn from, so the look cannot move before the outline exists. Keep the pick, or the default with the "unreviewed draft of its look" notice (`UNREVIEWED`, `look_unreviewed` app.js:4920).
- **Brand audit blockers.**
  - Keep them inside repair rounds (`audit_round`).
  - Keep them holding automatic delivery (`_holding` engine.py:1121 → `review_policy.held`).
  - Keep them shown on their slide card.
  - **Deliver** with blockers open must say so and ask, as a sheet listing them. Today a person may approve over them; keep that, but make it explicit.
- **Delivery as PowerPoint or Google Slides,** including the fallback `NOT_CONNECTED` (deliver.py:39), later **Deliver to Google Slides** (`deliver_again`), and numbered revisions (`deliver.again`).
  - **Deliver** is the brand's `final` checkpoint. It must stay a person's act bound to the deck hash on screen, as `expected_deck` already does for review_draft (engine.py:1793). deck_flow's HOSTS comment explains why (deck_flow.py:58-60).
- **Team claim.**
  - Every desk action must go through `self._held(path)` / `team.ours` like `decide` (engine.py:1845-1904).
  - Reclaim a delivered deck before changing it (`self._take` at 1889).
  - Desk results must settle only on the driving computer (Blog's `_guard` in `_settle`, desk_jobs.py:1527).
- **Old-deck guarantees:** the original is never changed (existing.py `SOURCE`), and the verbatim rule at Brand only and Polish (`STRICT`, build.py:105). Selection edits there must go through `pptx patch`, or be refused with a sentence.

### 5.6 What the stops and review levels become
| Today (stages.PIPELINE) | On the desk |
| --- | --- |
| gate:classify (document) | Start step 3 option plus a line on the Outline tab: "Read as material. Read it the other way" (`_reclassify`, engine.py:2046, priced) |
| gate:classify (existing deck inventory) | The original slide pictures appear in the desk cards' "Before" from the first render |
| gate:research-plan | Gone: the plan comes from the form's questions, as supplied-only synthesis already does with no job (runner.md "Supplied-only synthesis") |
| gate:research | A Research panel on the desk (findings, gaps, Leave out → outline + looks redraw, priced by `_leave_out_price` engine.py:2038) |
| gate:outline | Outline tab; no wait |
| gate:look | A pause in progress when the person chose to pick; else the brand's default, with a receipt |
| gate:build | Replaced by the desk; **Deliver** is the approval |
| rehearse (never runs) | A Finishing tool |

- **Review levels:**
  - The shared `review.level` in studios-config still governs Training Studio and saved Presentation runs.
  - For desk decks, map it only to the look: Automatic draft = brand default, Balanced and Step by step = pick.
  - Alternatively drop it for desk decks, as Blog's desk does (`stop='review'` fixed, desk.py:470).
  - `review_policy.automatic`'s presentation branch (C/review_policy.py:122-125) and deck_flow `GATES['presentation']` stay for old runs.
  - A desk deck's gates continue with a receipt `by: 'desk'` (like `review_policy.receipt`, 140-147), never `by: person`.
- **Copy to rewrite:** "Only you approve. A deck moves past a stop only by your decision" (P/docs/runner.md:129) becomes: intermediate work continues as your start chose, and delivery is yours.

### 5.7 How saved decks keep working
- Mark new decks `form.flow = 'desk'`, as Blog's `record['flow']`. `stages.steps` keeps today's pipeline for every run without it. `review_policy.level` already returns step_by_step for runs with no policy (review_policy.py:71-80).
- A deck waiting at a gate stays in the gated page until delivered.
- A delivered or finished deck offers **Open on the desk**, which builds the desk from outline.json and the last build round (`work/build/state.json` rounds[-1].slides, preview pictures, drawn section files).
  - Only the computer that built it has `work/`. Elsewhere the desk must say so, as `_say_again` already does ("There is no drawing of this deck on this computer…", engine.py:2083-2086). It offers "Draw it on this computer", priced by `_last_build`.
- Old decks without `questions` in a round already read `critic.LEGACY` (build.py:1437). Without `sections` in state, they cannot take slide notes. Gate that by `rounds` present.
- The desk must refuse gate routes for desk decks, and gate pages must refuse desk routes for gated runs. Blog: `ON_DESK` / `refuse_on_desk`, desk.py:19, 215.
- Revisions continue (`run['revisions']`, deliver.json `revision`). Publishing tags `presentations/<id>/r<n>` are unchanged (team.py:295).

## 6. What could be shared with Blog's desk (core/studio_core and ui-kit), ranked by what is lost if copied
The serving route already exists. `C/server.py:472-475` serves `C/deck_web/*` to every studio page built with `for_product`: Presentation (scripts/server.py), Training (scripts/desk.py) and Blog (scripts/management.py). Presentation and Training already load `deck-panels.js`/`.css`. Blog's desk itself imports nothing of its own from core: only `research_contract`, `research_sites` and `model_profiles` (desk.py:402-403, tool_jobs.py:85). ui-kit/style.css and markdown.js are vendored byte for byte into each studio.

1. **The version store.** Move Blog's desk.py:1005-1080 (`_versions_path`, `_entries`, `keep`, `versions`, `counts`, `restore`) into `C/versions.py`. It is studio-agnostic: a part-keyed jsonl, a cap of 20, session coalescing, torn lines tolerated, a symlink refusal. The `SOURCES` list becomes a caller argument.
   - Presentation keys parts by slide id and stores the composition slide beside the text.
   - Copying it would fork the history format.
2. **The per-part stale check and the job basis rule.**
   - Move into `C/desk_core.py`: `desk.checked` (666-681), `changed[part] = revision` in `_write` (627-663), and the job's `basis` fingerprint compare (desk_jobs.py `fingerprint` 206, `STALE` 74, `_apply` 1431-1490).
   - Presentation today uses one-off signatures per stop (`_direction_signature`, engine.py:2802; `expected_deck`; `NOTE_CHANGED` 245).
3. **The step-time estimate.** Move into core and use it for deck desk steps instead of last-try-only `_redo`:
   - `desk_jobs._times_path`, `_note_time`, `expected_minutes` (median of the last 20 times on this computer), `_timing` with `over` (1195-1290);
   - `desk.estimate` / `MINUTES` (389-395).
   - It sits beside `C/stops.py` `took`/`cost`/`lasted`, which Presentation and Training already share.
4. **The word diff and the History sheet.** Move into `C/deck_web/desk-kit.js` (served like deck-panels.js):
   - from B/assets/management/desk.js: `deskWords`, `diffWords`, `deskCompare`, `deskAge` (15-40) and `sDeskHistory` (502-513).
   - Presentation's compare adds the before and after pictures (the `.pair` markup from `buildPanel`, app.js:4985-4993).
5. **The selection bar.** Move into desk-kit.js plus CSS: `sDeskSelected`, `sDeskSelectionBar`, `sDeskBarContent` (desk.js:479-516) and `.desk-selection` (blog.css:185-186, 193).
   - The bar is glass, fixed, and sits above the tab bar on a phone, as the Selection and Glass layout rules ask.
   - The `ACTIONS` prompts (desk_jobs.py:40-46: rephrase, shorten, expand, fix) and the `_request` author-instruction wrapper (252-262) go to a `C/desk_prompts.py`.
6. **The Finishing panel shell and proposal sets.**
   - Page: `sDeskPanel`, `sDeskFinishOpen/Close/Tool`, `sDeskFloating`, `sDeskLayout`, `sDeskSheetOpened/Closed` (desk.js:611-660, 894-899), plus the CSS `.desk-layout.desk-finishing`, `.desk-finish`, `-head`, `-body`, `-sheet` (blog.css:209-217). These become a shared wide / drawer / phone-sheet panel.
   - Server: `desk_finish.keep`, `_latest`, `_prune`, `read`, `sets`, `forget`, `apply`, `skip` (desk_finish.py:42-300) become a core "proposals" module. Each studio supplies `present(item)` and `apply(item)`. Blog's are text swaps. Presentation's are a section repair, a notes write or a composition patch.
7. **Desk layout CSS.** Move into ui-kit/style.css as shared `.desk-*`:
   - `.desk-layout`, `.desk-column`, `.desk-aside`, `.desk-part-head`, `.desk-text`, `.desk-note`, `.desk-working`, `.desk-problem`, `.desk-stale`, `.desk-versions`, `.desk-version`, `.desk-compare`, `.desk-plain del/ins` (blog.css:170-201).
   - ui-kit's own rule is that a page stylesheet "never draws" a shared control (docs/design/golden-gate.md:91-95).
   - Without the move, deck.css would copy about 30 rules.
8. **Progress copy and clock.** Move `sDeskEstimate`, `sDeskClock`, `sDeskSpent`, `sDeskProgress` (desk.js:268-292) into desk-kit.js ("Nothing needed from you. … opens here when it is ready, in about N minutes."). This gives one sentence in every studio. It works with C/stops.py `lasted`.
9. **Create once per page operation.** Blog's `desk._create` (1123-1175) uses an operation ID plus a request fingerprint, so a retried Start returns the same blog. Presentation's `Engine.start` (engine.py:725) has its own same-moment claim handling. Worth a shared helper for the create step only.
10. **Already shared; keep it so:**
    - research choice: `research_sites.effective`, `research_contract.snapshot`;
    - model profiles: `model_profiles.snapshot`;
    - the look picker: `C/deck_web/deck-panels.js` `lookPicker`, used by the desk's look card in progress;
    - `C/stops.py` for honest time and cost.

**Do not share:**
- **Job queues.** Blog's `tool_jobs` is a single worker with result JSON. Presentation's `Engine`/`jobs.py` uses sandboxed workers with `worker_tools` and runs steps in parallel. Share the basis/settle rule, not the queue.
- **Text split/join and proofread.** desk.py `split`/`join` by `##` and desk_finish proofread are Markdown-specific.

**A precondition for 4–8:** Blog's desk.js is built on runner.js helpers (`sNode`, `sAdd`, `sButton`, `sOpenSheet`, `sChoice`). Presentation's app.js has its own (`make`, `add`, `card`, `capsule`, `chip`). Shared desk-kit.js must take its DOM helpers as deck-panels.js does (its own `make`, and the page passes `picture()` in), or ui-kit must gain one small helper file first.

### 5.8 Additions from the page walk (sections 1–4)
- **Look choice at start, for every route that draws looks.** Scratch, document, Redesign and Full rework all draw looks. Today Balanced silently uses the default for Redesign (§1.1). The desk's start "Look: pick when drawn / brand default" must cover them all, and the receipt must name the choice, not a review level.
- **Interruptions that stay on the desk.** A worker's question (`questionPart`), a failed or timed-out step (`problemPart` with Try again or Give it more time), a spend limit (Resume) and a team clash stay. They are not stops, but they need the person. Put them first on the progress screen and the desk, above the cards (§4.1 order).
- **Deliver on the desk.** Download must exist wherever the deck can be opened. Either commit the delivered .pptx, or say on every computer but the maker's that only the maker's computer has the file (§1.2). Give revisions one meaning: delivery revisions, with publish as a tag on one of them (§2).
- **Fold the notes into one.** The desk's single per-slide note replaces "Ask for changes to this slide", "Change what it says", "Send slide feedback", "Note for the next step" and the outline row's "Ask for changes" (§2). Keep "Change what it says" as a choice inside the note: redraw the slide, or change its words in the outline.
