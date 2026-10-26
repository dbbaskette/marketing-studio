# Piece 5: the deck desk in Presentation Studio

**Date:** 2026-10-26, at main cc53056. **Owner's words:** "Lets apply our UI changes to blog
studio to the other studios. We also need to do an audit of workflow and clean it up", and,
asked whether that meant the layout rules or the writing desk as well: "1 and 2".

This is piece 5 of `2026-10-26-workflow-audit.md`. Its main input is section 5 of
`2026-10-26-workflow-audit/presentation.md`. Every claim taken from there was checked
against the code at cc53056, and the commands were checked against Harness Slides 0.16.0.
The desk is built on piece 3's shared desk (`core/studio_core/drafting` and
`ui-kit/drafting.js`). This spec names the parts of piece 3 it uses by what they do, because
piece 3's spec is being written at the same time.

## Decisions for the owner

Each choice below comes with a recommendation. The rest of the spec assumes the
recommendation.

1. **What the shared review level means for a desk deck.** *Recommended:* nothing. On a
   desk deck the start form's **Look** choice is the only setting left. It is either "Pick
   it when the samples are drawn" (the default) or "Use the brand's default look". The
   shared level still governs Training Studio and saved Presentation runs. *Other choice:*
   map Automatic draft to the default look and the other levels to the pick. That keeps the
   level meaningful a little longer, but it is a setting the person cannot see from the
   form.
2. **What Review the deck does with what it finds.** *Recommended:* show each finding on
   its slide as a proposal with **Apply** (redraw that slide's section with the finding as
   the note, priced) or **Skip**. This is Blog's Finishing rule: nothing changes until
   Apply. *Other choice:* keep today's behaviour after "Check the deck", where major and
   critical findings send their sections back by themselves for up to two rounds.
3. **The research plan.** *Recommended:* when Harness Research has synthesis, a desk deck
   takes its plan from the form's questions with no job, as supplied-only research does
   now. A deck with no questions gets one built from its goal. With the legacy question
   queue, the plan job still runs, with no stop. *Other choice:* always run the plan job,
   with no stop.
4. **A word edit that no longer fits its slide.** *Recommended:* save nothing. The card
   keeps the new words and offers **Redraw with these words**, priced, or **Discard**.
   *Other choice:* save the words and mark the slide "words not drawn yet" until it is
   redrawn. That leaves the outline and the picture saying different things.
5. **Word edits at Brand only and Polish.** *Recommended:* refuse them with a sentence,
   because these levels promise your deck's words exactly. Speaker notes may still be
   edited, since they are not shown on a slide. *Other choice:* allow the person's own
   typed edits and refuse only the assistant's (Rephrase, Shorten, Expand).
6. **How an unreviewed delivery is labelled.** *Recommended:* stop adding "— first draft,
   not checked" to a desk deck's Google Slides title and "-unreviewed-first-draft" to its
   file name. Instead the Deliver sheet says plainly whether the deck was reviewed, and
   deliver.json records it. *Other choice:* keep the labels. Every desk deck is
   unreviewed until Review the deck runs, so every desk delivery would carry them.
7. **Rehearse.** *Recommended:* run it in process only. It counts the words in the notes
   against the form's minutes, slide by slide. The optional "likely audience questions"
   job is left out of this piece. *Other choice:* add that job now.
8. **The whole-deck note.** *Recommended:* keep the deck's parallel redraw, three sections
   at once (`AT_ONCE`), with **Stop** and "N of M sections". *Other choice:* one section at
   a time, as Blog does. That is slower by the clock, but each section's note sees the
   one before it.
9. **Blockers from the brand check at Deliver.** *Recommended:* deliver over them only
   after a sheet lists each one with its slide and the person confirms. This is today's
   freedom, made explicit. *Other choice:* refuse to deliver while a blocker is open.
10. **Decks started from chat.** *Recommended:* keep them on today's gated pipeline until
    piece 7. Only the page's start makes desk decks in this piece, as Blog's desk did at
    first.

## What is wrong now

### A note on a slide needs a stop, and every note redraws through a stop

- A slide note exists only at the deck's stop. `_decided` refuses it otherwise with "The
  {it} is not waiting for a decision now." (`runner/engine.py:237`, raised at 1927). The
  only exception is a delivered deck.
- Each note reopens `gate:build` through `stages.reopen`. `_ask_again` then sends the named
  sections back (`engine.py:2179`, `_sections_for` 1831). The deck runs whole, review,
  repair and render again and stops again.
- The part worth keeping already works. `section_work` names the focused slides, freezes
  the others as `unchanged_slides`, and says "Copy all other slides in your section exactly,
  including their drawing." (`runner/steps/build.py:1254`). `kept` refuses any change to a
  frozen slide with "this slide has no requested repair. Keep its drawing unchanged."
  (`build.py:350`).
- A note changes only the drawing. Every redraw is told "What a slide says stays as it was
  approved: change how it is drawn." (`build.py:1227`). The words change only through
  "Change what it says", which reopens the outline (`_say_again`, `engine.py:2069`).
- Notes sent while a section is drawn are never used up. `build_feedback` items without
  `late` are kept for good (`engine.py:1955`), and `section_work` adds every one for the
  section to every later redraw of it (`build.py:1196`).

### Five names for one note

The deck screen says "Ask for changes to this slide" (`desk/app.js:3458`). It also says
"Change what it says" (3472) and "Send slide feedback" (4845). The progress screen says
"Note for the next step" (3577), and the outline row says "Ask for changes". The desk needs
one note per slide.

### Words, speaker notes and history

- **Composed decks have no text edit.** The words live in `outline.json`. `kept` holds the
  drawn text to them. "The studio never edits a slide file itself." (`docs/runner.md:131`).
- **Speaker notes redraw a section.** `notes` is one of `DRAWN_FROM` (`build.py:1071`). A
  section whose notes changed is therefore not kept by `_kept` (1079), and its composer
  draws it again.
- **The original deck's notes cannot be patched.** `pptx patch` never touches the notes
  part. `pptx compare` reports a change to it as `unselected-package-part-changed`
  (Harness Slides `scripts/lib/pptx-edit.py:171-175`).
- **No slide keeps an earlier version.** `draw_whole` deletes every older `whole-*` folder
  (`build.py:1505`). `build.start` clears the start folder, `told/`, the previews and the
  whole folders, and writes a fresh state (`build.py:973-1049`).

### A teammate's copy redraws the whole deck unasked

When `work/` is missing on this computer, `_settle` (`engine.py:1021`) quietly marks every
build step to run again. A deck taken over at its stop is drawn again in full, with no
price shown first.

### The deck check repairs by itself, and labels every first draft

- After "Check the deck" (`review_draft`, `engine.py:1787`), `keep_review` sends each
  section with a major or critical drawing finding back for up to `REPAIRS = 2` rounds
  (`build.py:1826`, `97`).
- Under `user-first` the delivered title gains " — first draft, not checked"
  (`runner/steps/deliver.py:46`). The download is named `-unreviewed-first-draft`
  (`engine.py:2490`).

### The look under review levels

- Under Automatic draft, `look.choose_default` records "Automatic draft: the brand's
  default look, {name}, was used." (`core/studio_core/deck_flow.py:85`, used at
  `runner/steps/look.py:310`).
- On a desk deck the person chooses this at the start, so the receipt must name that
  choice, not a review level.
- Piece 1 fixes Balanced skipping the look for Redesign.

### Rehearse never runs

It is a gate labelled "Rehearse (coming later)" (`runner/stages.py:72`) that `survey`
skips.

### What already works and stays

These are reused as they are:
- section reuse after an outline edit (`_kept`, `DRAWN_FROM`);
- live previews (`build_progress`, "Slides taking shape", `app.js:4827`);
- repair rounds from the preview screen and the brand check (`preview_repairs` 1379,
  `audit_round` 1628), which need no person;
- review reuse for unchanged slides (`reusable_review` 1692);
- the patch path for Selected changes (`existing.patch_work` 484, `apply_patch` 570,
  `pairs` 627);
- the prices said before a redraw (`_redo` 3135, `_last_build` 3215);
- the look samples and picker (`look.draw_looks`, `deck_web/deck-panels.js` `lookPicker`);
- delivery and its revisions (`deliver.upload`, `record`, `again`, and
  `Engine.deliver_again` 3437);
- the team claim (`_held`, `hold`, `_take`, `team.ours`).

## The design

### Saved and new decks

- **The marker.** A deck started from the page's start gets `run['flow'] = 'desk'`. The
  check is `decks.on_desk(run)`. Every deck without it keeps today's pipeline and
  screens, unchanged.
- **Both directions refuse.**
  - On a desk deck, `decide` and the gate routes refuse with `desk.ON_DESK`: "This deck
    is on the desk. Change it there."
  - On a gated deck, the desk routes refuse with `desk.NOT_ON_DESK`: "This deck is not on
    the desk. Use its own screen, or open it on the desk once it is finished."
  - This is Blog's `ON_DESK`/`refuse_on_desk` (Blog `desk.py:19`, 215).
- **Same pipeline.** A desk deck runs the same `stages.PIPELINE` as any other. What
  changes is how its gates are met (see "What the stops become").

### The start: three steps, then Start

The start is piece 4's numbered sheet, opened from **New deck**. It has three steps.

1. **Kind of deck.** Three cards: an idea, a document, an existing deck.
   - Choosing an existing deck shows its five levels on the same step: Brand only, Polish,
     Redesign, keep content, Full rework, and Selected changes. Selected changes adds its
     box: "Which slides, and what to fix".
2. **Sources and settings.**
   - **Research.** On or off. Where it may look: your documents, your sites and/or the
     public web, through the existing `research_sites` choice. It comes with up to eight
     research questions (`decks.research_questions`). An existing deck has no research
     (`decks.check_form` refuses it).
   - **Minutes, audience, talk or handout, brand and variant, output.**
   - **Look.** "Pick it when the samples are drawn" (the default) or "Use the brand's
     default look". The look card is shown for every route that draws looks: idea,
     document, Redesign and Full rework.
   - **Assistant and model,** folded under **Options**, as now.
   - There is no review-level card and no "first draft" choice. Every desk deck is built
     with `initial_review: 'user-first'`, so the critic runs only from Finishing.
3. **What you have.**
   - Title and goal.
   - For an idea, the brief.
   - For a document, the document itself, with an optional line: "It lays out the slides"
     or "It is material to build from". The line replaces the classify stop. Left unset,
     the classify job reads the document.
   - For an existing deck, the deck itself.

**Start** sends the form with `flow: 'desk'` and `look: 'pick'` or `'default'`. With the
document override it also sends `reading: 'spec'` or `'material'`.

### Progress: no stops, except a look pick the person chose

- The progress screen uses piece 3's progress line and clock. Its first line is "Nothing
  needed from you. The deck opens here when it is ready, in about N minutes."
- N is piece 3's step-time estimate for deck steps on this computer. With no record yet,
  the line says instead: "This computer has no record yet of how long that takes."
- Below the line are the current step in words (`Step.doing`), "Slides taking shape" with
  its live previews, and one note box per preview. The box is labelled "How should this
  slide change?" and its button is **Send note**. It uses `build_feedback` as now.
- **The look pause.** It comes only when the person chose to pick the look.
  - The look card leads the progress screen with "One thing needs you: pick the look. The
    deck is drawn in it." and the shared `lookPicker`.
  - Picking continues the deck. The pick is a pause: nothing else on the screen asks for a
    decision.
- **Interruptions come first, above everything else.** These are:
  - a worker's question (`questionPart`);
  - a failed or timed-out step (`problemPart`, with Try again or Give it more time);
  - the spend limit (Resume);
  - a team notice.
- **Arrival.** The deck reaches the desk the first time `gate:build` waits. From then on
  the desk is its screen, including while desk work runs.

### What the stops become

| Today (`stages.PIPELINE`) | On a desk deck |
| --- | --- |
| `gate:classify`, document | Continues with a desk receipt. The start's override, when given, sets the reading and the classify job is skipped. The Outline tab says "Read as material" (or "as a script for the slides") with **Read it the other way**, priced as `_redo('gate:classify')` says. |
| `gate:classify`, existing deck | Continues. The original pictures become each card's Before. |
| `gate:research-plan` | Continues. The plan comes from the form (decision 3). |
| `gate:research` | Continues. The research is shown in the Research panel on the desk (piece 5's fourth pull request). |
| `gate:outline` | Continues. The outline is the desk's Outline tab. |
| `gate:look` | Waits only when the start chose to pick. Otherwise the brand's default is chosen with the receipt "You chose the brand's default look at the start: {name}." (`look.START_DEFAULT_WORDS`). |
| `gate:build` | The desk. Its waiting state is the desk's resting state, and **Deliver** is the approval. |
| `rehearse` | A Finishing tool. The gate is never reached, as now. |

- **The desk receipt.** A gate a desk deck continues past gets
  `{'gate', 'by': 'desk', 'evidence': fingerprint, 'at', 'decision': 'continued-on-the-desk'}`
  in `review_events`, and the gate is marked `by: 'desk'`. It is never marked
  `by: person`. This parallels `_policy_gate` (`engine.py:1133`) and is a new
  `Engine._desk_gate`.
- **No review level.** A desk deck stores no `review_policy`, so `review_policy.level`
  reads `step_by_step` for it. Nothing on the desk path consults the level. Any older code
  path that does would stop at the gate, which is the safe side.
- **Review levels stay for saved work.** The shared `review.level` still governs Training
  Studio and every saved Presentation run. Its controls go in piece 7.
- **Two sentences change.** `docs/runner.md:129` says "Only you approve. A deck moves past
  a stop only by your decision". For desk decks this becomes: "On the desk, the steps
  before your deck run as your start chose. Delivering is always yours."

### The desk

- The desk uses piece 3's layout: a reading column and an aside, with a glass toolbar. The
  cards are opaque reading surfaces.
- **Toolbar:** **Deliver** (the one filled button), **Download**, **Finishing**, and a
  More menu with Pause, Stop, Undo where it can work, Publish, Take over or Hand over, and
  Delete.
- **Tabs:** **Slides** and **Outline**.
- **Above everything:** interruptions, then the progress line while desk work runs. The
  line reads, for example, "Redrawing section 2 (slides 4 to 6)" or "Redrawing: 2 of 5
  sections", with **Stop**.

#### A card per slide, grouped by section

- Cards sit under section headings. The sections are the ones `outline start` made: runs
  of up to four content slides (Harness Slides `scripts/lib/outline.mjs:210`).
- Cover, section and closing slides are lead slides. They get cards too, but no note box,
  because no composer draws them.
- Each card shows:
  - **The picture**: the last round's preview (`picture(kind='build')`). An existing deck
    also shows its **Before**.
  - **The words**: title, subtitle, points, caveat and source, from `outline.json`. They
    are read-only in the first pull request and editable from the second.
  - **Speaker notes**: read-only in the first pull request and their own edit from the
    second.
  - **Findings**: the brand check's blockers and warnings for this slide, and the
    review's findings once Review the deck has run. These are what `buildPanel` shows now
    (`app.js:4916`).
  - **Note.** The box "How should this slide change?" with **Redraw slide N**, and below
    it the price line.
  - **History** (from the second pull request).
- A slide whose section is being redrawn shows "Redrawing…". Its controls are disabled,
  and a note for it is refused with a sentence until the redraw ends.

#### The slide note

The slide note redraws only the slide's section, through `section_work`.

- **The note is kept.** `desk_note(path, number, note, expected)` adds
  `{id, slide, number, section, note, at, by, status: 'waiting'}` to `run['desk_notes']`.
  It also adds the section to `state['asked']['sections']` as a union, so other asks are
  kept.
- **The deck is reopened.** When the deck rests at `gate:build`, the action reopens it
  (`stages.reopen(record, 'gate:build')`). When it is delivered, `deliver.again` sets
  deliver.json aside first, and then only that section is asked.
- **What runs.** The chain is `build-sections` (that section) → `build-whole` (merge,
  compile, preview, brand check) → `build-review` (skipped under `user-first`) →
  `build-repair` (only preview or brand-check repairs) → `build-render`. Then `gate:build`
  waits again, which means the desk.
- **What the composer sees.** `section_work` reads only the waiting and drawing notes for
  its section. It marks the noted slides as the focus, and every other slide in the
  section is frozen. `keep_section` marks those notes `done`. The old `build_feedback`
  items are moved to `run['build_feedback_done']` when the deck first arrives on the
  desk, so a redraw never repeats them.
- **Notes on other sections queue.** A note for another section while one redraws is
  added to the ask, and `build-sections` or `build-repair` draws it in the same chain. A
  note for the section being redrawn is refused with "Slide {n} is being redrawn now.
  Your note is kept here; send it when that ends."
- **The basis rule.** A desk word edit adds one to `build_feedback_revisions[section]`. A
  composer still working on that section from before is then superseded (`jobs.py:490`),
  so a result lands only while its section is unchanged. This is piece 3's basis rule,
  served by the counter the engine already keeps.
- **The note may ask for new words.** In the first pull request the line under the box
  says: "A note changes how the slide is drawn. To change its words, edit them on the
  Outline tab." From the second pull request the words are edited on the card itself.

#### The whole-deck note

- The top box, "How should the whole deck change?", has **Redraw every section**. It asks
  every section with the note at once. The composers run three at a time (`AT_ONCE`).
- The progress line says "Redrawing: N of M sections".
- **Stop** stops the jobs under way, the way Stop does now. It waits for them to end, as
  delete does (`STOP_WAIT`), and then:
  - takes the sections not redrawn yet off the ask;
  - marks their notes `set aside`. Each such card shows "Not redrawn: you stopped the
    whole-deck note." with **Redraw slide N**;
  - clears the halt and wakes the deck, which puts together what was redrawn.
- A section that fails leaves the others done, and its card shows the problem.

#### Honest prices before a redraw

Every redraw button has a price line under it, worked out on the server.

- **A slide note.** `desk.section_price(record, section)` adds up:
  - the last kept try of `build-sections:<section>` (seconds and dollars);
  - the last tries of `build-whole` and `build-render` (seconds; they are runner steps);
  - said with `stops.cost`.
- **The sentences.**
  - With a record: "Redraws section 2 (slides 4 to 6); the other slides stay exactly as
    they are. Then the deck is put together, rendered and checked. Last time this took
    {cost}."
  - With no record: "… This computer has no record yet of what it costs. Expect minutes,
    not seconds."
  - It never says "$0.00": `stops.cost` says "the assistant reported no cost".
- **The whole deck.** The note's price is `_last_build`, said as `wholeDeckSays` says it
  now.
- **The step-time estimate.** When piece 3's estimate has a median for the action on
  this computer, the line adds "Usually about N minutes here."

#### Selection edits (second pull request)

- **The bar.** Selecting text in a card's words shows piece 3's selection bar: Rephrase,
  Shorten, Expand, Fix and Ask…. The words are slide text, so the result must still fit.
- **For a composed deck** (idea, document, Redesign, Full rework):
  1. A small words job (`briefs/words.md`, through `Engine._agent`, with no worker tools)
     rewrites the selected passage of one field: title, subtitle, a point's label or text,
     caveat or source. Its prompts are piece 3's shared selection actions.
  2. The new outline is checked with `outline check` (`outline.apply_edits`).
  3. `words.patch_section` puts the same text into the drawn section JSON. Title,
     subtitle, caveat, source and notes are slide fields there. A point's words are
     canvas text nodes, and the old text must match exactly one of them.
  4. `worker_tools.check_section` runs `kept` and `compose compile` without `--output`.
     This is the fits check, which refuses rather than shrinks ("shorten the text, split
     the slide or restructure", Harness Slides `scripts/lib/compose.mjs:491`).
  5. If it fits, the patched section is kept as a new drawn file, and the deck is put
     together, rendered and checked. No composer job is needed.
  6. If it does not fit, or the old text is not found exactly once, nothing is saved
     (decision 4). The card shows the new words with "These words do not fit the slide as
     it is drawn." It offers **Redraw with these words** (the slide note's price) or
     **Discard**. Redrawing saves the words and redraws the section, telling the composer
     which slides' words changed since its brief was written.
- **In-place typing** follows the same chain without the words job. It saves one second
  after the last keystroke, against the part revision the form saw (piece 3's per-part
  stale check).
- **Selected changes** decks use `pptx patch`. A selection or a typed edit inside one run
  of one top-level shape becomes one operation `{slide, object, expectedHash, runs:
  [{index, text}]}`, or `text` for a single-run shape. It is added to the deck's plan, and
  `apply_patch` applies the whole plan to the original, followed by `pptx compare`.
- **Brand only and Polish** refuse word edits (decision 5) with "This deck keeps your own
  deck's words exactly. Change them in your deck, or start again at Redesign, keep
  content." A slide note that only changes the drawing still works.

#### Speaker notes as their own edit (second pull request)

- **Each card's notes box saves without a composer.** The chain is:
  1. the outline's `notes` (outline check);
  2. the drawn section's slide `notes` (`words.patch_section`, field `notes`);
  3. `check_section`;
  4. the deck is put together and rendered (merge, compile, preview, brand check,
     render).
- **The whole deck is put together again because** `compose render` writes the notes page
  (Harness Slides `pptx-native.py:722-729`), and the delivered file is the preview's deck
  (`draw_whole`).
- **Edits made while the deck is being put together** join a single following pass. They
  do not each start one.
- **Selected changes** decks refuse a notes edit: "Speaker notes in your own deck are kept
  as they are. Selected changes changes only the text on the slides." Brand only and
  Polish allow it.

#### History per slide (second pull request)

- **The words are shared.** Before any change to a slide's words or notes, the slide's
  words are kept in `desk/versions/<slide-id>.jsonl` in the deck's folder, which the team
  shares.
  - Each entry is canonical JSON of title, subtitle, detail, points, caveat, source and
    notes.
  - The store is piece 3's version store, with this studio's list of sources: `save`,
    `selection`, `note`, `redraw`, `restore`, `outline`, `finishing`, `open`. It keeps 20
    versions a part and merges an editing session into one version.
- **The drawing stays on this computer.** The slide's composition object and picture go
  to `work/desk/versions/<slide-id>/<entry-at>.json` and `.png`. Like `work/`, these are
  never shared.
- **Compare** shows the word diff (piece 3's compare, run on the words written as lines),
  plus the before and after pictures where this computer has them.
- **Restore** puts back the words and, where this computer has it, the drawing.
  - With the drawing, the composition object goes back into its section, followed by
    `check_section` and a fresh put-together and render. No assistant runs.
  - Without the drawing, the words go back by the word-edit chain. If they no longer fit,
    the card offers the priced redraw.
  - A restore is itself a version.

#### The Outline tab (first pull request)

- **The tab is today's outline editor** (`outlinePanel`, `app.js:4555`): rename, reorder,
  add and remove slides, and edit each slide's words. It comes with its storyboard
  (`storyboard`, `engine.py:2857`, through `outline draft`).
- **Save** runs `outline.apply_edits` (outline check), then `build-start`, which keeps
  every unchanged section (`_kept`). The changed sections are drawn, and the deck is put
  together and rendered.
- **The price is said before Save.** "N sections change and are redrawn; the rest stay as
  drawn." It is priced as the sum of `section_price` for the sections that change. A
  reorder that moves slides between sections changes those sections.
- **The tab also holds:**
  - the reading line for a document deck ("Read it the other way", priced);
  - **Change the look** (look samples drawn again, then a pick, then every section drawn
    again, priced by `_last_build`).

#### Add a source (fourth pull request)

- **Adding.** An aside like Blog's. **Add a source** takes a file or pasted text through
  `documents.add` or `add_text`. The source is listed under Sources with its title.
- **What reads it:**
  - the words jobs (Expand reads the sources);
  - the speaker-notes proposals;
  - the outline when it is written again.
- **Research is not run again unless asked.** **Research again with it** says the price
  first, the way the research stop prices a research change now (`research_view.price`).
- **The Research panel** sits in the same aside. It shows the findings and gaps, and
  **Leave out**, priced by `_leave_out_price` (`engine.py:2038`): "Leaving findings out
  redraws the outline and the look samples without researching again."

#### Finishing: preview, then apply (fourth pull request)

Finishing is piece 3's panel shell. Every tool proposes, and nothing changes until Apply.
Proposals are kept with piece 3's proposals module, with this studio's `present` and
`apply`.

- **Brand check.** Runs in process, with no assistant. It shows the last render's audit,
  per slide: blockers first, then warnings. **Check again** runs the brand skill's audit on
  the current deck in seconds. **Apply** on a blocker redraws that slide's section, with
  the blocker as the note, priced.
- **Review the deck.** The reviewer job (`review_work`), priced by the last `build-review`
  try where there is one.
  - Findings arrive per slide as proposals (decision 2). `keep_review` does not send
    sections back on a desk deck.
  - **Apply** is a slide note made from the finding's note and fix. **Skip** keeps the
    finding as read.
  - When the review lands, `review_requested` is cleared, so later slide notes are not
    reviewed again by themselves.
- **Speaker notes.** A job (`briefs/speaker-notes.md`) proposes notes for each slide from
  its words, the outline and the sources. Each proposal shows the old and new notes.
  **Apply** writes them through the notes edit, with no redraw.
- **Rehearse.** Runs in process. It counts the words in each slide's notes at 150 words a
  minute, against the form's minutes, and shows the total and the slides that run long:
  "Slide 4's notes take about 2 minutes; the deck's notes take about 31 of your 25
  minutes." A deck with no minutes shows the time alone.

### What must stay

- **The look choice.** `look choose --outline` refuses an outline that changed since the
  samples were drawn ("The outline has changed since the samples were made"), so the look
  cannot come before the outline. A desk deck keeps the pick, or the brand's default with
  the start's receipt. Samples nobody saw rendered keep `deck_flow.UNREVIEWED` on the desk.
- **Brand check blockers.**
  - They stay inside the repair rounds (`audit_round`) and keep holding automatic
    delivery (`_holding`).
  - They are shown on their slide card.
  - **Deliver** with a blocker open opens a sheet that lists each one with its slide:
    "The brand check found {n} problem(s) that block delivery. Deliver anyway, or fix
    them first."
  - The confirm sends `blockers_seen`, a fingerprint of the list shown. A list that has
    changed since is refused with "The brand check changed since this page read it. Look
    again before you deliver."
- **Delivery and its revisions.**
  - **Deliver** is the brand's `final` checkpoint and stays a person's act. It is bound to
    the deck hash on screen (`expected`, as `review_draft` binds it at `engine.py:1793`).
  - It is refused while desk work runs: "Your last change is still being put together.
    Deliver when it is done."
  - It uses `deliver.upload` and `record`: Google Slides, or PowerPoint with
    `NOT_CONNECTED`.
  - **Send to Google Slides** (`deliver_again`) stays.
  - Any desk change to a delivered deck runs `deliver.again` first. The desk then says:
    "Delivered as revision 2. A change here makes revision 3, delivered when you press
    Deliver."
- **The team claim.**
  - Every desk action goes through `_held` and `hold`, as `decide` does.
  - A deck this computer delivered is taken back with `_take` before it changes.
  - Desk work runs only where `team.ours` holds, because `_work` returns otherwise, so a
    result settles only on the driving computer.
  - **On a computer that lacks `work/`,** a desk deck does not redraw itself. `_settle`
    leaves its build steps alone. The desk shows the shared words and the shared contact
    sheet with "There is no drawing of this deck on this computer." and **Draw it here**,
    priced by `_last_build`.
- **Existing decks.** The original is never changed (`existing.SOURCE`). Selected changes
  edit text only through `pptx patch` and `pptx compare`. Brand only and Polish keep the
  words exactly (`STRICT`, `build.py:105`).
- **Interruptions first,** on the progress screen and on the desk.

### How saved decks keep working

- A deck without `flow: 'desk'` keeps the gated pipeline, its stops and its screens. A
  deck waiting at a gate stays on its gated screen until it is delivered.
- **Open on the desk** (fifth pull request) is offered on a delivered deck.
  - It needs this computer's last build round (`work/build/state.json` `rounds[-1]` with
    `start.sections`). Without it, it says: "There is no drawing of this deck on this
    computer. Draw it here first, or open it on the computer that made it."
  - It sets `run['flow'] = 'desk'` and `run['opened_on_desk']`. It keeps one version of
    each slide's words (source `open`). It marks the gates the deck passed as they were.
    Opening twice returns the same desk.
  - The delivered revision stays delivered until a change is made. The first change runs
    `deliver.again`, as any later desk change does.
  - A deck whose last round has no `questions` reads `critic.LEGACY` as now
    (`build.py:1437`).
- **Revisions and publishing do not change.** These are `run['revisions']`, deliver.json
  `revision`, and the tags `presentations/<id>/r<n>` (`team.py:295`).

## Delivery: five pull requests, each usable on its own

1. **The desk for decks from an idea or a document.**
   - It brings the marker and the refusals both ways, the desk gates with receipts, and
     the start's look choice with the look pause.
   - It brings the progress screen, the slide cards, the slide note, the whole-deck note
     with Stop, the prices, the Outline tab, and Deliver with the blockers sheet.
   - It brings the team-claim and missing-`work/` behaviour.
   - In this pull request, an existing deck still starts on the gated form.
2. **Words on the desk.** In-place word edits, selection edits, speaker notes as their own
   edit, and History per slide.
3. **Existing decks on the desk.** The five levels at the start, Before and After, Selected
   changes through `pptx patch`, and the word rule at Brand only and Polish.
4. **Sources, research and Finishing.** Add a source, the Research panel, and Finishing:
   the brand check, Review the deck, speaker notes and rehearse.
5. **Open on the desk** for delivered decks, plus the docs and guidance that describe the
   desk.

## Out of scope

- **Piece 1:** the broken paths and copy, assumed merged.
  - Balanced and Redesign showing the look.
  - The delivered PowerPoint reachable from another computer.
  - Undo offered only where it works.
  - "That's wrong" priced.
  - The "Sign in on Status" lines.
- **Piece 2:** the shared runner modules and the deletions, including the rehearsal
  placeholder bead.
- **Piece 3:** the shared desk parts in `studio_core/drafting` and `ui-kit/drafting.js`.
  These are consumed here, not built:
  - the version store;
  - the per-part stale check and the basis rule;
  - the step-time estimate;
  - proposals;
  - History and compare;
  - the selection bar;
  - the Finishing shell;
  - the progress line;
  - the numbered sheet;
  - the desk styles.
- **Piece 4:** the layout rules and shared components, assumed merged.
- **Piece 7:** chat starting desk decks, and retiring the gates, the review-level
  controls and the legacy research queue.
- **Not planned:** real-time token streaming, editing a .pptx by hand, and a fact check
  against sources.

## Testing

- Disposable data folders (`PRESENTATION_STUDIO_DATA`), workspaces, Git identities and
  studios-config files, as `tests/helpers.py` and `runner_support.StudioCase` set them.
- Scripted workers (`runner_support.Workers`) and the stand-ins for Harness Slides, the
  brand skill and Harness Research. No provider job, no network, no Google.
- **Engine tests** (`tests/test_deck_desk.py`):
  - a desk deck from an idea reaches the desk with no gate waiting and a desk receipt on
    each gate;
  - the look pause, and the default look's receipt;
  - a slide note redraws one section, with the others byte for byte the same;
  - notes queue across sections, and a note on a busy section is refused;
  - the whole-deck note, and Stop;
  - prices, including no record;
  - Deliver bound to the deck hash, the blockers sheet's fingerprint, and revisions after
    delivery;
  - the team claim from a teammate's computer;
  - no silent redraw without `work/`;
  - gated decks refused on the desk and desk decks refused at the gates.
- **Word tests** (`tests/test_desk_words.py`): a patch that fits lands with no worker job;
  one that does not fit saves nothing; a point found twice falls back; notes edits; the
  patch plan for Selected changes; the Brand only refusal.
- **History tests:** shared words and local drawings; restore with and without the
  drawing.
- **Finishing tests** (`tests/test_desk_finishing.py`): the brand check view; review
  findings as proposals with no repair; speaker-notes Apply with no composer; rehearse
  counts.
- **Page journeys** (`tests/test_desk_page.py` through `page_harness.js`): the start in
  three steps, progress with the look pause, a slide note with its price, the whole-deck
  note with Stop, Deliver with blockers, the Outline tab, a selection edit, History, and
  Finishing. The page tests also check that no forbidden word is shown.
- **Route tests** (`tests/test_flow_routes.py`): every route on the desk start, including
  each existing-deck level.
- The full Presentation Studio suite, from `studios/presentation/tests`, before each merge.
  Run it on the shared Tart runner where ports are needed.
