# Phase 2 of the authoring workflow review: honest copy and one vocabulary

**Date:** 2026-10-22, at main 21a216e (after Phase 1, PRs #77 and #79). **Owner's words:**
"write the spec for phase 2,3,4,5. Then write the implementation plan for each."

This is Phase 2 of `2026-10-21-authoring-workflow-review.md`. It has three parts: one word
for each thing in all three studios; stops and cost shown before they happen; and copy that
says what the page does. It adds no new step and no new research behaviour. Line references
are to main 21a216e.

## Already done in Phase 1

These review findings were fixed by PRs #77 and #79 and are not repeated here:

- Try again at research says what it does ("continues from the saved draft and runs up to 3
  more rounds…; the last 3 rounds took…") in all three studios. "Try again re-runs Do the
  research from the start" is gone.
- A step out of time says "ran out of the time a step may take… That limit, 15 minutes a
  step, is in Settings, under Limits." with **Give it more time and try again** (core
  `stops.timed_out`, Blog `sTimeWords`).
- Running out of money mid-step is the budget stop with Carry on, never a failed try, and no
  job starts below `stops.floor`.
- A CLI failure names **Status → Check this computer**; Blog offers **Open Status**.
- Blog: **Finish** always opens "Finish this blog?" and names the library side effect; the
  "Open Edit manuscript" hint shows only for a blog with a manuscript; **Continue without
  research** exists.
- Research shows "Round 2 of 3"; research jobs are attributed to the research step.
- Presentation's research stop opens `research/review.md` with **Read every objection**.

## What is wrong now

### Stops are set somewhere else, and the form's way there loses the form

- Every start form has a stops line with a **Change** link to Marketing Studio's onboarding
  page: Blog `runner.js:43` (`sStopsLine`, `change.href='/onboarding/#'+token`), Presentation
  `app.js:2864` (`stopsLine`), Training `app.js:4387`. Following it is a full navigation; the
  form is held only in page memory and is lost.
- Training already has a per-training "Review level" card on the last step
  (`app.js:4341 reviewLevelCard`), with "Shared default: Balanced. This training keeps the
  level it starts with." beside the Change link, and under Options: "The review preference is
  shared with Marketing Studio and is saved when this training starts." (`app.js:4415`). Two
  controls, one of which leaves, and a sentence that is not true (nothing is saved to the
  shared preference when a training starts).
- Blog and Presentation take the shared level only (`blog_runner.py:1166`
  `review_policy.snapshot(shared)`; Presentation `engine.py:748` `review_policy.capture()`).
  The form cannot choose for one run.
- No studio's Settings shows the review level. Blog Settings has only "Change shared settings"
  (`runner.js:156`), which also leaves.
- The shared save path refuses a stale assistant or model, but not a stale review level:
  `preferences.save`'s guard checks only `models` and `assistant` (`preferences.py:146`).

### Nothing says what is next, or what it has cost

- Blog: the run says "Each step may take up to 10 minutes; cost is not tracked for a CLI
  account." (`runner.js:227`). Phase 1 meters research jobs only (`synthesis_research.py:131`
  `blog_worker.metered()`); outline, draft, review and package jobs are not metered, though
  Claude Code reports cost for each.
- Presentation and Training record seconds and dollars for every attempt (`jobs.attempts`,
  `engine.attempts`) but the run screen says neither how many steps remain nor where it next
  stops for the person. The stops line exists only on the start form; after start, Blog's
  `sRunStops` lists every stop but not which is next.
- Ask for changes is priced nowhere. Presentation says "No slides marked: the whole deck is
  drawn again (about $7.20 and 18 minutes, as the last build took)." only on a delivered deck
  (`app.js:1260`, `!gate`); at the deck stop with nothing marked the same request says nothing.

### Stops are miscounted or misnamed

- Training, step by step: "A deck adds two reviews per level when this computer can build
  it." (`app.js:4397`). A deck stops three times: its outline, its look and the deck itself
  (`deck_flow.PAUSES['step_by_step'] = ('draft', 'look', 'final')`). `gatesFor`
  (`app.js:4192`) counts no deck gate at all.
- Presentation, Balanced: "Balanced: it stops for the outline and the deck" (`app.js:2858`),
  but the first stop is "Review the direction" (`stages.py:123`), which holds the research,
  the outline and the look together.
- Presentation names the look stop four ways: stage "Brand" (`app.js:69`), step "Check the
  brand" / "Waiting for you to check the brand" (`stages.py:52`), stops line "the brand"
  (`app.js:2857`), panel "Choose the look" (`app.js:4338`).
- Training calls its first Balanced stop "the direction review" (`reviews.py:99` "Review the
  direction"; `app.js:4381`, `4393`). It holds the research report, every blueprint, guide,
  brief, outline and look picker. Its approval sheet says "Approving the direction writes the
  learner guide and brief for each of the 4 levels" (`app.js:5664`), but those were written
  before the stop: `reviews.commits` lists every wanted stage except the deck
  (`reviews.py:137`), including `document` and `brief`, which are in `PREPARED`.

### One thing, many names

- Blog's last stage: "Export package" (`blog_runner.py:63`, `STAGE_WORDS` "the export
  package" `runner.js:8`), "Packaging" (`DOING`), "handoff notes" (`runner.js:249`), and
  "Finish". The worker prompt already calls it "a publication handoff".
- Blog's team action: **Publish revision** (`runner.js:224`) opens a sheet that says "Record
  this approved blog in the team repository. Nothing is sent to a CMS or made public."
  (`runner.js:306`), beside **Mark as published** (`runner.js:852`) for a real publication.
- Blog's upload and library roles: "Facts (may be quoted)", "Example of the kind of post",
  "Examples of the kind of post", "voice sample", "examples of a kind of writing (style
  samples)", "Retire this style" beside "kind of post" (`runner.js:647`, `900`, `968`, `626`).
- The research choice has six wordings: Blog Settings "Selected sources only / Sources plus
  public research / No research" (`runner.js:161`); Blog new blog "No research / Selected
  sources only / Selected sources and public web" (`runner.js:181`); Blog existing draft "No
  new research; use saved evidence / Research selected sources / Research selected sources and
  public web" (`runner.js:397`); Blog from files "Also research the web to fill gaps"
  (`runner.js:1014`); Training "The public web / Your documents only / Both" (`app.js:177`);
  Presentation "Research it first" (`app.js:2867`).
- Presentation's first-draft option: "Show first draft before AI review", "AI critique and
  polishing" (`app.js:2932`), "Unreviewed first draft" (`4412`, `4491`), "Use/export draft
  as-is" (`5230`), "Run AI review" (`4498`), "Delivered — unreviewed first draft" (`4633`),
  "Choose normal AI review or show the first draft before AI review." (`decks.py:146`), and a
  delivered title " — Unreviewed first draft" (`steps/deliver.py:44`). The build step that
  this skips is called "Check the deck" (`stages.py:63`).

### The page says what it does not do

- Preview pool: "Google Drive: each deck keeps one presentation named “Preview: …” in your
  Drive, written again at each render." (Presentation `app.js:160`, Training `app.js:214`,
  `3371`). With Harness Slides' `google-preview-pool` (`slides.py:461`) every deck shares a
  few pool presentations and no file is named for a deck.
- Blog "Ready to start": "Research uses only the sources you allow." (`runner.js:179`) also
  when no source is selected and no research runs (`sResearches`, `runner.js:36`).
- Blog gate ledes: "Read the draft. Use it when ready, then polish the wording." and "Read the
  feedback, then return to the manuscript to make changes." (`runner.js:254`). The gate has no
  polish control and no way back to a manuscript.
- Blog Ask for changes: "Your changes are noted. The next version comes back for your review."
  (`runner.js:263`). Under Balanced or Automatic the stage asked about may not be a stop.
- Blog tone: the hint says "Tone is a nudge on top of the voice." (`runner.js:181`); the runner
  drops the usual tone whenever a voice is chosen (`blog_runner.py:1031`) and the page never
  says so.
- Blog has three free-text channels (Note for the next step, Ask for changes, Tone) and only
  the note says when it is used.
- Blog README: "Choose **Write a blog**, **Outline only**, **Revise a draft**, or **Review a
  draft**" (`README.md:71`). Home offers Polish a document, Write from a brief, Use my
  outline, Explore ideas, New blog from my files and Interview me (`runner.js:311`).
- Presentation: "Rehearse with Yoodli · Coming later" in every deck's timeline (`app.js:70`,
  `3392`; `stages.py` `rehearse`).
- Presentation classify stop: toggling **That’s wrong** (`app.js:3755`) leaves the toolbar's
  **Approve** unchanged, so the person approves what they just said was wrong.
- Presentation existing deck: **Ask for changes** at the inventory stop sends a note to a code
  step (`inventory`) that reads no note.
- Presentation: a Google Doc link on the document route is accepted with no Google sign-in;
  only an existing deck is checked (`engine.py:735`). `existing.NOT_READY` says "Sign in to
  Google on the Check this computer screen" (`steps/existing.py:78`); the screen is Status.
- Presentation: a deck asked for as Google Slides becomes PowerPoint when Google is not
  connected (`steps/deliver.py:76` `NOT_CONNECTED`), said only after delivery.
- Presentation shows "Render 3f2a1c9b0d4e" under each progress slide (`app.js:4420`), "Recent
  model jobs … Reported actual model: …" and "Preview timing" (`app.js:4469`) on the deck
  screen, and "The runner could not go on: ValueError: …" (`engine.py:1069`).
- Presentation toolbar decisions pass no problem line (`decide('approve', '', null, approve)`,
  `app.js:5235`), so a refusal lands in the toast at the head of the deck.
- Training money: the now-line says "stops at $20.00" (`app.js:767`) from the settings limit
  after Carry on has raised it (`engine.py:2941` `cleared`). "a deck of this size has cost
  about $7.20" (`app.js:5670`) is `deck.RATE` times slides (`deck.py:600`), not anything this
  computer spent.
- Training research stop: "objections are listed in its research review
  (reviews/research.md)" (`engine.py:3199`) with no button to open it.

## Design

### 1. Where this run stops, on the form and in Settings

Each start form's stops line becomes a card, **Where this run stops**, with the three levels
as one segmented control (Balanced, Automatic draft, Step by step), the sentence of what the
chosen level stops for in this run, and one chip: **Use this for new work in every studio**.

- The control sets this run's level only. It starts at the shared level the form read.
- The chip, when on, writes the level to the studios-config file under its lock when the run
  starts, and is refused when the file's level differs from the one the form read: "Another
  studio changed where new work stops. Reload the page and try again." Nothing is started.
- No Change link. Nothing on the form navigates away.
- Training's existing "Review level" card becomes this card; its "Shared default: …" sentence
  stays; the sentence "The review preference is shared with Marketing Studio and is saved when
  this training starts." goes.
- Each studio's Settings shows **Where new work stops** with the same control, saved at once
  through the same refusal. Marketing Studio's onboarding page keeps its control.

One shared function holds the write: `review_policy.change(update, level, seen)`. The shared
save path's guard (`preferences.save`) also refuses a stale `review` the same way.

### 2. Next stop, steps left, and cost on every run

Each run's view gains `ahead`: steps left, the next stop for the person under the run's own
level, and what the run has spent so far (seconds, and dollars when every job reported them).
The run screen shows one line under the beads:

> 4 steps left · Next stop: the outline · So far 12 minutes and about $1.40

- "Next stop" comes from the policy itself (`review_policy.ahead`), never from a copy of its
  rules in the page. A gate that may still be held for a grave finding is not counted as a
  stop; the line says "Next stop" only for gates the level always stops at.
- Dollars are said only when every job reported them; otherwise "the assistant reported no
  cost" (Codex), as Phase 1 already says for research.
- Blog meters every stage job, not only research, with `blog_worker.metered()`, and keeps each
  job's seconds, tokens and dollars on the run as `jobs`.
- The Blog run line "cost is not tracked for a CLI account" is replaced by the `ahead` line.

### 3. The price of a change, in its sheet

Every Ask for changes sheet says, before it is sent, which steps run again and what they took
the last time they ran: "Drawn again: the outline and every step after it, 6 steps. Last time
they took 22 minutes and about $3.10." Where nothing is recorded yet: "Drawn again: …; this
computer has no record of what they cost."

- Presentation at the deck stop with no slide marked says the whole-deck sentence it already
  says on a delivered deck.
- Research change requests keep their own wording; pricing "Revise the research" is Phase 3.

### 4. Stops counted and named right

- Training, step by step: "A deck adds three stops per level: its outline, its look and the
  deck." `gatesFor` counts three per deck level.
- Presentation, Balanced: "Balanced: it stops for the direction (the research, the outline
  and the look together) and the deck". The stops line comes from the same `stopsFor`, with
  `gate:outline` named "the direction" under Balanced.
- Presentation's look stop is **Look** everywhere: stage "Look", step "Choose the look",
  "Waiting for you to choose the look", stops line "the look". The action **Choose another
  brand** keeps its name: it chooses a brand.
- Training's first Balanced stop is **Review the first drafts** (step label, stops line, card
  title, sheet title). Its approval sheet lists only what approving starts: the materials not
  yet written (practice scenarios, Yoodli layouts) and the deck, or "Nothing more is written
  for the levels: approving carries on to the deck." `reviews.commits` leaves out `PREPARED`
  stages.

### 5. One word per thing

| Thing | One name | Replaces |
| --- | --- | --- |
| Blog's last stage | Handoff ("the handoff", "Writing the handoff") | Export package, Packaging, handoff notes |
| Blog's team action | Record in team repository | Publish revision |
| Material that may be quoted | Facts | Facts (may be quoted) stays as the choice label |
| Material that shows a shape | Examples ("Example of the kind of post") | Example(s) of the kind of post, examples of a kind of writing |
| An author's own posts | Voice samples | voice sample (unchanged) |
| What a learned kind of post was learned from | Style samples | style samples (unchanged); "Retire this style" becomes "Retire this kind of post" |
| Research choice | No research · Only what you supply · What you supply and the public web (Training adds The public web only) | the six wordings above |
| Presentation research chip | Research the public web first | Research it first |
| Presentation look stop | Look | Brand, Check the brand, the brand |
| Presentation first draft | First draft, before the check: form chip "See the first draft before the deck is checked"; state "First draft, not checked"; button "Use this first draft"; action "Check the deck"; delivered "Delivered: first draft, not checked" | the eight wordings above |

Stored values do not change: stage ids, file names (`derived/blog-package.md`), `research`
values, `initial_review` values and the `rehearse` gate id stay as they are, so saved runs
read as before.

### 6. Copy that says what the page does

- Preview pool: with the pool, "Google Drive: previews are drawn in a few shared
  presentations named “Preview: …” in your Drive, reused by every deck. <Studio> never deletes
  them."; without it, today's sentence. The setup view says `previews.pool`.
- Blog "Ready to start": "No new research." / "Research reads only the N sources you
  selected." / "Research reads your selected sources and the public web." / for supplied-only
  with nothing selected: "No research runs: no source is selected."
- Blog gate ledes: draft "Read the draft. Use it to go on, or ask for changes."; review
  "Read the review. Its findings go to the handoff; to act on one, ask for changes to the
  draft."
- Blog Ask for changes, sent: "Your changes are noted. The next <stage> comes back for your
  review." when that stage is a stop under the run's level; else "Your changes are noted. The
  <stage> is written again and the run goes on to <next stop>, where you see it."
- Blog's three channels each say when they are used, one sentence each: Ask for changes
  "writes this stage again with your words"; Note for the next step "goes with the next job and
  changes nothing already written" (kept); Tone "With a voice chosen, the usual tone is left
  out; a tone you type here is added as a nudge."
- Blog README lists Home's real start choices. The missing Home cards are Phase 4.
- Presentation timeline has no Rehearse row. The `rehearse` gate stays in the pipeline data.
- Presentation classify stop with **That’s wrong** on: Approve reads "Take it as <other
  kind>" and the gate line says so.
- Presentation existing deck: no Ask for changes at the inventory stop; the gate line says "To
  read another deck, stop this one and start a new deck from it."
- Presentation start: a document from a Google Doc link is refused before anything is made
  when Google is not signed in, with `existing.NOT_READY`, which now names "Status → Check this
  computer".
- Presentation: when Google Slides is chosen and Google is not connected, the start form's
  Options and the deck stop say "Google is not connected on this computer, so approving makes a
  PowerPoint file. Sign in on Status and Deliver to Google Slides afterwards."
- Presentation: no render hash under a progress slide; "Recent model jobs" and "Preview
  timing" move into a closed disclosure **Details for troubleshooting**; an unexpected error
  says "The runner could not go on: <message>." with the exception's class kept only in the
  run's log.
- Presentation: a refusal of a toolbar decision is shown in the gate's own problem line, which
  takes focus.
- Training: the now-line says "stops at" the run's own limit (`limit + cleared`), sent by the
  runner as `spent.stops_at`. The direction sheet's estimate says "estimated at about $7.20 and
  40 minutes of agent time for a deck of this size (a fixed estimate, not this computer's
  history)".
- Training research stop: a **Read every objection** button opens `reviews/research.md`, as
  Presentation's does; the sentence names no path.

## Out of scope, and the phase that owns it

- Phase 3: what the research gate shows, research triage, a research source boundary on the
  form, what the research control does (including Blog's Home cards forcing `research='none'`),
  pricing **Revise the research**, replacing planning jobs.
- Phase 4: Home cards for outline only and revise/review; downloads; Pull the Google Doc;
  Apply the review's findings; real checks in "Checked for you"; requiring a look pick; moving
  guide and brief after Training's first stop (which would change what "Review the first
  drafts" holds); the scratch route's notes box.
- Phase 5: companion versions and capabilities, delivery live by default.

## Testing

Tests use disposable settings (`STUDIOS_CONFIG`, `HOME`), workspaces and data roots, and no
provider jobs.

- Core: `review_policy.change` writes under the lock and refuses a stale level, a missing file
  reads as Balanced, an unreadable file refuses; `review_policy.ahead` agrees with
  `automatic` for every product and level; `preferences.save` refuses a stale review level;
  `stops.cost` words.
- Each studio: the start form sends `review_level`, `review_seen`, `review_default`; the run
  keeps its own level; the default is written only with the chip and refused when stale;
  Settings saves the level; no form has a link to `/onboarding/`.
- Each studio: the run view's `ahead` (steps left, next stop, spent) for each level; the page
  line; Blog metering of a stage job through the real worker path with a scripted CLI.
- Copy: page journeys assert the new strings and the absence of the old ones listed above.
- Training: matrix rows for the review-level choice and the first-drafts approval.
- Root `tests/test_ui_consistency.py`, Blog `scripts/measure_guidance.py --check`, each
  `validate_package.py`.
