# The authoring workflow in every studio: review

**Date:** 2026-10-21, at main 58e23d5. **Owner's words:** "fully review the workflow for each
studio in the UI and make it a smooth authoring process with clear and understandable
process and instruction. Include reviewing Tanzu Brand and the harness-* skills to make sure
we are fully utilizing the workflow and capability."

Four read-only reviews fed this document: one per studio, walking every path a person can
take on the page from the first card to a finished piece, and one inventory of every
capability of Harness Research 1.0.0, Harness Slides 0.16.0 and Tanzu Brand 0.14.0 against
what the studios call. Line references are to main 58e23d5. Two specs written earlier the
same day are taken as given and not repeated: research checks that can read originals
(`2026-10-21-research-originals-design.md`) and announcement writing
(`studios/blog/docs/superpowers/specs/2026-10-21-announcement-writing-design.md`).

## What is the same in all three studios

Six things recur, and fixing them once each is most of the work.

1. **The research step is the weakest link, everywhere.** It can fail for a studio reason
   and tell the person it is a research reason (the originals bug, 31 jobs on one deck);
   it shows the person a hash and a report instead of the brief, the gaps and the
   checker's assessment it already has; it never says what a round costs or what "Try
   again" will do; its "Ask for changes" is the most expensive request on any page and is
   priced nowhere; and the plan stage still speaks the language of the old
   question-by-question queue that the synthesis workflow replaced.
2. **The page says what it does not do.** "Try again re-runs Do the research from the
   start" (it resumes from the saved draft); "Research uses only the sources you allow"
   (when no source is selected, no research runs); "Approving the direction writes the
   learner guide" (it was written before the stop); "A deck adds two reviews per level"
   (three); "each deck keeps one presentation named Preview:" (four shared pool files);
   "Rehearse with Yoodli · Coming later" in every deck's timeline.
3. **Failure cards name no recovery.** A timeout says "did not work in 3 tries" and never
   that the limit is a setting; running out of money mid-step is counted as a failed try;
   a CLI failure points at no screen; a research refusal lists forty objections with one
   cause.
4. **Costs and stops are hidden until they bite.** No page says how many steps remain,
   what the next stop is, or what a decision costs before it is sent. Review levels live
   on the Marketing Studio onboarding page; the "Change" link on a studio's start form
   leaves the form and loses it.
5. **One thing, many names.** Export package / Handoff notes / Finish / package; Brand /
   Look / Choose the look / Choose another brand; sources / files / references / library /
   examples / samples; three wordings for the research choice; five labels for the deck's
   first-draft option.
6. **The companions are called, but half-read.** Writers are never told about code spans,
   so technical decks set commands in Arial; decks default to reading delivery although the
   brand says a talk is live; the research brief that Harness Research authors for the
   writer never reaches the writer in Presentation Studio; Presentation decks cannot carry
   a picture; three different minimum versions of Harness Slides coexist, and the brand's
   installer keeps a 0.15.1 that silently loses every 0.16.0 feature.

## Blog Studio

### Path map

Balanced stops at the first writing stage, the last stage and always at angles.

| Entry | Stages | Stops | Ends |
| --- | --- | --- | --- |
| New blog from my files, Find three angles | angles → (research) → outline → draft → review → package | angles, outline, package | Finish → Done card; draft kept in the team library |
| New blog from my files, I know the point | (research) → outline → draft → review → package | outline, package | same |
| Write from a brief | research only if chosen and sources ticked → outline → … | outline, package | same |
| Use my outline | (research) → draft → review → package | draft, package | same |
| Explore ideas | outline as "Ideas" → develop → outline → draft | outline, draft | an unreviewed draft: no review, no package |
| Polish a document | editor: polish, check facts, review argument, revise | none | save edits, download, send feedback to Google |
| Interview me | question sheet → outline → Use my outline path | draft, package | same |
| Revise or review a draft | no Home card: five taps through the legacy table | review or draft, package | same |

### Blocks authoring

- **A research failure on a new blog is a dead end with a wrong hint** (runner.js:200). The
  card says "Open Edit manuscript to polish the writing without research"; a new blog has
  no Edit manuscript button, and no action removes research from the run. Add "Continue
  without research" (a `skip-research` run action); show the editing hint only for an
  existing draft.
- **The research stop promises saved work that was deleted.** The refusal says "The draft
  report and the check's notes are saved for correction"; on the page path the case lives in
  a temporary directory that is cleaned up (blog_runner.py ~1540-1633). Keep the case under
  the blog, list the objections on the run screen, and apply the originals spec's
  short-circuit and grouping to the blog path too.
- **Three of the four start choices the README names are not on Home.** "Outline only",
  "Revise a draft" and "Review a draft" exist in `BLOG_MODES` but not as cards. Add cards or
  fix the README.
- **First-run setup hides every default and never warns about a missing assistant.** The
  assistant defaults to Codex; `run-options.agents` says which CLIs exist and the page never
  reads it; every step then fails with "The selected CLI failed. Check its sign-in and
  usage, then retry." Open Writing preferences on setup, grey out an uninstalled assistant,
  and point CLI failures at Status.
- **Finish approves and shares with no confirmation under Balanced and Automatic**
  (runner.js:211), then toasts "Approved. The next stage can begin." Always open the
  "Finish this blog?" sheet at the last stage; it names the library side effect.

### Confusing or slow

- The review stage is advisory and nothing applies it: findings arrive folded at the final
  gate, and fixing them means "Ask for changes → Draft" and three more jobs. Offer "Apply
  the review's findings" as a minimal-edit draft job.
- Settings → Research is dead for runs started from a Home card (runner.js:147 sets
  `research='none'`); the "Ready to start" card claims research that will not run when no
  source is ticked.
- The review aside ("Checked for you", "Worth a look", "What changed") is collapsed on every
  gate; "Checked for you" shows two always-true rows and hides the lint findings the worker
  gets; "Worth a look" renders a raw JSON preservation check.
- Stop points and review levels are two systems the person can touch from neither the run
  nor Settings; "Change" leaves Blog Studio; the run never says where the next stop is.
- Gate ledes name controls the gate lacks ("then polish the wording"; "return to the
  manuscript"); "Ask for changes" promises a review that Balanced will not give.
- Note for the next step, Ask for changes and Tone are three free-text channels with no
  sentence on when to use which; the default tone is dropped whenever a voice is chosen and
  the page never says so.
- Explore ideas ends at an unreviewed draft; every other path ends with review and package.
- Vocabulary: Export package / Handoff notes / Finish / package; Publish revision / Mark as
  published / "Publishing is a separate action"; sources / files / references / library;
  "Example of the kind of post" beside "Example of a kind of writing (style sample)"; four
  wordings of the research choice.
- The research-plan stage hands a chat module to a tool-less worker and costs a job for a
  hint; the writer is never told what `research_bundle` is, so it hedges and sprinkles IDs;
  `brief.md` and `evidence.md` never reach the person.
- Waiting is honest about the step and silent about the whole: no steps-left, no cost.
- "Keep in the team library" is order-dependent with no per-row way back; two blog lists
  with two sharing vocabularies; the Done card dead-ends at Markdown with Pre-publish and
  Repurpose hidden under Tools and no way to open the draft as a Google Doc from the page.

### Harness Research in Blog Studio

Used well: capture of readable facts and material, never examples; the author and
independent checker with the pinned helper; digests that stale later stages; the bundle
handed to outline, draft, review and package. Unused: the brief as the writer's input and as
something the person can read; refresh and targeted follow-up; comparisons for a comparison
style; `context: partial` for excerpted captures, which the author is told are whole.
Misused: the research-plan job; refusals that discard the case; the research gate's "Worth a
look" boilerplate instead of the checker's assessment and gaps; two research systems
documented side by side in `blog-deep-research.md`.

## Presentation Studio

### Path map

Three routes (from scratch, from a document, from an existing deck) through a two- or
three-step form, then: research plan → research → research report → outline → brand →
look → build (sections, whole, review, repair, render) → deliver. Balanced folds classify,
research and look into one "Review the direction" stop before the deck stop; Automatic
stops only for the deck. An existing deck adds inventory, extract and, for selected edits,
`pptx patch`. Every deck's timeline ends in "Rehearse with Yoodli · Coming later".

### Blocks authoring

- **Research from a document never passes** (the originals bug; spec exists). Page side,
  beyond the spec: render the refusal's objections as a list, not one paragraph; show the
  rounds while they run; price Try again.
- **A step that runs out of time stops after three identical tries**, and the page never
  says the limit is a setting. Say "It ran out of the time a step may take (N minutes, in
  Settings → Limits)" and offer "Give it twice the time and try again".
- **The scratch route promises a brief and has nowhere to write one.** The route card says
  "Say what it is about and who it is for"; the form takes a 120-character title, an
  audience and a takeaway. `notes` is plumbed end to end (decks.py, outline.py,
  research_steps.py) and never sent. Add the box.

### Confusing or slow

- Under Balanced, approving the direction needs a look pick, and nothing says so until the
  server refuses two screens above the picker. Disable Approve until a look is picked and
  count it in the tally.
- Under Balanced the research triage cards are replaced by the raw report, and "Request
  changes to the research" reruns the whole synthesis with no cost warning.
- Synthesis findings are shown as "N questions · N answered · 0 to look at" with empty
  question lines; "Research again" on one finding reruns everything.
- Research jobs are named so that `attempts()` cannot attribute them: the research row
  shows no tries, seconds or dollars, and "Try again re-runs Do the research from the
  start" is false (it resumes from the saved draft). Name them `research:author-1`,
  `research:review-1`, show "Round 2 of 3".
- "Ask for changes" at an existing deck's inventory stop goes nowhere: the inventory is a
  code step and notes reach only agent steps.
- A Google Doc link is accepted without Google sign-in and fails after the deck exists;
  Google Slides output falls back to PowerPoint silently.
- "Ask for changes" at the deck stop with no slide marked redraws every section; the sheet
  says so only after delivery.
- The look stop has four names across stage, step, panel, actions and docs.
- Editing the outline after picking a look silently redraws the looks and applies the pick
  to samples nobody saw.
- Research has no source boundary on the page: the plan's scope is always public web, so a
  confidential document with "Research it first" sends public queries built from it.
- The first-draft option speaks another language ("AI critique and polishing", "Render
  3f2a1c9b0d4e", "Use/export draft as-is").
- The reviewer gets only the eight questions; the brand's review checklist and the tool's
  review guidance never reach it, and the brand audit runs after review and repair, so its
  blockers land on the person instead of the repair rounds.
- "Redesign, keep content" has no design stop, although both companions assume one.
- Toolbar refusals land at the head of the deck, away from what failed.

### Polish

Settings never shows the review level; the sampled slide is never named at the look stop;
"That's wrong" and the Approve label disagree; model receipts and render hashes are shown to
the person; `existing.NOT_READY` names a screen that does not exist; after delivering your
own deck in a team workspace you must "Take it" to revise it; a bundle check surfaces as
"ValueError"; the README still says the pinned runtime is 0.14.1; fonts are never checked
although the brand's `doctor` knows; PowerPoint-by-choice decks cannot be sent to Google
later.

## Training Studio

### Path map

Set-up once (where trainings live, sharing, agent and model, brand, previews, limits), then
a three-step form (learning goal; materials, levels 101 to 401, deck, brand, time, brief
kind, copies and Yoodli; review level, sources, assistant). Then: documents → research plan
→ research → blueprint per level → per level: document, brief, deck (outline with a design
session, look, sections, whole, review, repair), scenarios, Yoodli → package. Balanced
writes every level's blueprint, guide, brief, outline and look samples before one
"direction review", then builds, then a final review. Each deck stops on its own.

### Blocks authoring

- **The research check cannot read a supplied original** (the originals bug; spec exists).
  The stopped card quotes "48 minutes and $9.80" for tries that could never succeed.
- **The "Change" link on the last form step throws the form away**: a full navigation to
  the onboarding page, with the draft held only in page memory, beside a card that already
  lets the person pick the level per training. Drop the link.
- **Nothing made can be downloaded from the page.** The deck gate says "This is not text,
  so it is not shown here. It is 2.3 MB. Open it from the training folder: ~/…/101/deck.pptx";
  copies say "Kept with the training as 101/document.docx"; there is no download route. Add
  `GET /api/download` for managed files and Download on the gate, Made so far, Copies and
  the index.
- **Running out of money mid-step is a failed step with an action that cannot work.** A
  `limit` ending with the budget error counts as a failed try; after three near-instant
  retries the card says "did not work in 3 tries" with Try again. Treat it as the budget
  stop with Carry on, never start a job with less than a floor left, and say that raising
  the limit in Settings is the other way on.
- **The Google Doc round trip is one-way on the page.** A teammate's edit in the Doc blocks
  the copy forever, and the only exit ("ask your assistant to bring those changes in")
  contradicts the page's own rule. Add "Pull the Google Doc" on the copies card.

### Confusing or slow

- The "direction review" is not a direction review: under its heading sit the research
  report, every blueprint, guide, brief, outline and look picker for four levels, and the
  approval sheet says approving will write the guides the person just read. Rename it,
  make the sheet list only what is still unwritten, and consider moving guide and brief
  after the stop so the first review is cheap.
- The research gate under the synthesis contract says less than the old one: a digest and
  "No automatic checks apply here"; `brief.md`, `evidence.md` and the checker's assessment
  never reach the page.
- The research-plan brief still describes a per-question queue the synthesis path does not
  run.
- "Ask for changes" on the research rewrites every blueprint, guide, brief and deck
  direction and reruns the author and the check; nobody is told.
- The stop card names a file path (reviews/research.md) and the page has no button to it.
- Stops per deck are miscounted as two in three places; it is three.
- "Finish this level, then wait" under Balanced pauses before a review that needs every
  level.
- Every deck is reading delivery; the live-or-handout choice the brand insists on is never
  asked.
- Money copy drifts: "stops and asks at $20.00" after Carry on cleared it; "a deck of this
  size has cost about $7.20" is a constant rate, not this computer's history.
- A timeout says only "did not work in 3 tries".
- The deck's words decision is also a twenty-slide design document, because the design
  session runs on every deck where the brand reserves it for explicit walkthroughs.
- Set-up asks for three numbers with no sense of scale.

### Polish

Stale lines in `docs/runner.md` (the look step "is not in the runner"; harness-slides
0.14.1); "Depth and reference brief" holds only the brief kind; two sentences about the
review level contradict each other; the research plan appears in the direction review with
no text; Approve's "what happens next" is a four-second toast; the Yoodli copy buttons exist
only on a gate Balanced skips; the beads have no bead for the combined review; the brand
audit's small-text warning on every caveat line could be settled with the audit's
exceptions file.

## The companions: used, unused, misused

### Used well

Harness Research's synthesis workflow (save, independent review, verify, up to three
rounds, pinned helper version, digests that stale later stages) in all three studios.
Harness Slides' outline contract and checks, compose pipeline, split-point audit,
provenance notes, preview repair clusters, the Google preview pool, `pptx inspect/patch/
compare` for existing decks, Drive import. Tanzu Brand's contract export and check,
deck-direction.json, `look samples` and `look choose`, `guidance start --brand`, icons by
id, the presentation audit with blockers holding the gate.

### Unused, ranked by what a person gains

1. **Code spans.** No brief tells a writer to backtick names, commands and fields, so
   technical decks set them in Arial and `unmarked-code` findings reach a worker that does
   not know what they mean.
2. **Live delivery.** Both deck studios hard-code `reading`; a talk gets the smaller body
   size and no notes screening, against the brand's own intake rule.
3. **The research brief as the writer's input.** Presentation Studio rebuilds passages
   from `facts.json`; Training hands the report; nobody hands `brief.md`. Comparisons are
   never requested, so a comparison deck never gets a criterion-aligned table.
4. **Pictures on Presentation decks.** The asset manifest and image generation are wrapped
   in `P/slides.py:630-676` and never called; cover layouts with a picture slot are avoided.
5. **PDF export completeness** for Training handouts, where notes carry answers.
6. **Parallel previews.** A global lock serialises previews that the pool could run in
   parallel.
7. **Refresh research** (`synthesis-reuse.md`): no studio can refresh stale evidence; stale
   only blocks.
8. **Originals for public PDFs and HTML**, so the checker can attest them (the spec).
9. **A design stop for Presentation's "redesign, keep content"**, or an agreed statement
   that there is none.
10. **Tanzu Brand `--voice-profile`** on Blog's contract export; `look samples --slide` to
    choose the sampled slide; the audit's `--exceptions` once images appear; `doctor` in
    Status for fonts.

### Reimplemented

The critic's eight questions are copied into `build.py` and `deck.py` with three wording
drifts, while the tool writes them into `critic.json`. `ready()` re-checks soffice,
pdftoppm and Drive instead of calling `doctor`. A throwaway-case `save` stands in for
`synthesis validate` (blocked until Harness Research 1.0.1 ships). The legacy
question-queue research and Blog's `deep_research.py` live on beside the synthesis path,
and both deck studios still draft thirty planning questions with the legacy brief.

### Version drift

`pins/companions.json` is current (Harness Research 1.0.0, Harness Slides 0.16.0). But the
floor is `>=0.14.1`, `MINIMUM` in both `slides.py` files is 0.13.1, Training tells people to
update to 0.15.1, and Tanzu Brand's own installer pins Harness Slides 0.15.1. A machine where
the brand was installed first keeps 0.15.1 and every capability gated by `KNOWS` disappears
without a word. Presentation Studio waits for a `progress-events` capability that 0.16.0
does not list. Tanzu Brand is unpinned. The brand's guidance still names "Presentation
Studio's design session", which only Training has.

### Instructions that contradict a companion's own guidance

- The author payload says "never invent paths such as research/sources/"; `investigate.md`,
  handed to the same worker, says "save a faithful readable capture in `research/sources/`".
- Training's section brief says "never set one of several peers larger, bolder or in
  another colour"; Harness Slides says "name the focal node; one emphasis per slide".
- Both deck studios say a deck "is read alone as well as presented"; Tanzu Brand says a
  talk defaults to live and the outline carries `delivery`.
- Presentation's section brief says to ignore what the tool's guidance says about previews
  and critique, while handing the worker that guidance.
- Harness Research says to give a delegated worker its stage reference, not the library;
  the contract hands the author three references including one addressed to a studio.
- Harness Slides asks for per-slide proposals before building; Tanzu Brand says none is
  needed; the two deck studios resolve this differently.
- Blog's brand handoff says to pass `--voice-profile`; the code never does.

## The plan, in order

Five phases. Each is one pull request or a short series; the first two unblock people
today, the rest make the process legible and then fuller.

### Phase 1: research that can finish, and failures that say what to do

The two specs already written, then the cross-studio pieces they do not cover:
- Research originals (spec and plan exist): readable originals, distinct originals only,
  the short-circuit, grouped objections, round cost. Apply the same to Blog Studio: keep the
  refused case, list objections, no deleted "saved work".
- Research jobs attributed to the research step in all studios: tries, seconds, dollars,
  "Round n of 3" on the page, and an honest Try again sentence.
- Timeout and budget stops: "ran out of the time a step may take (N minutes, in Settings)"
  with "Give it more time"; budget exhaustion mid-step becomes the budget stop; CLI failures
  point at Status.
- Blog: "Continue without research"; Finish confirmed at every level.

### Phase 2: honest copy and one vocabulary

- One word per thing: Handoff (not Export package); Look (not Brand); facts, examples, voice
  samples, style samples; one three-option research control; "Record in team repository".
- Stops and cost in the open: a "Where this run stops" control on each start form that writes
  the shared level, "Next stop" under the beads, steps left and cost on every run, the price
  of a change request in its sheet, three stops per deck, no "Change" link that leaves the
  form.
- Copy fixes with the page's actual words: the stops lines, the direction review's name and
  approval sheet, the preview pool sentence, the first-draft option, "That's wrong" and its
  button, existing-deck "Ask for changes", Google sign-in at the form, the Yoodli
  placeholder.

### Phase 3: the research stop worth stopping for

- Show the brief, the evidence and the checker's assessment (coverage, usefulness, gaps) at
  the research gate in every studio; map findings to the planning questions; write the
  plan brief for the synthesis path.
- Research triage under Balanced (Presentation); "Leave out" counts; "Revise the research"
  priced; a research source boundary ("your documents only / plus the public web") on every
  form.
- Replace the planning job with scope fields where supplied material is all there is
  (Blog's claims map; the deck studios' questions as hints).

### Phase 4: finish the authoring loop on the page

- Download or open every deliverable (Training); "Pull the Google Doc"; "Open as a Google
  Doc" for a blog; Pre-publish and Repurpose on the Done card; Home cards for outline-only
  and revise/review.
- Apply the review's findings as a minimal edit (Blog); open review asides; real checks in
  "Checked for you".
- Balanced's direction review: require and signal the look pick; keep edits from silently
  redrawing looks; consider guide and brief after the stop (Training).

### Phase 5: the companions, fully used

- Raise the Harness Slides floor to 0.16.0 everywhere (pins, both `MINIMUM`s, Training's
  `RELEASE` and `NAMES`); pin Tanzu Brand; drop the dead `progress-events` path.
- Code spans in every outline and section brief; delivery live by default for talks, asked
  once; the critic's questions from `critic.json`; the brand audit before review so blockers
  feed repairs; the reviewer given the review guidance.
- `brief.md` to the writers; comparisons when the goal compares; pictures on Presentation
  decks through the asset manifest; parallel previews; `doctor` in Status; `--voice-profile`
  for Blog; refresh research.
- Resolve the design-session split with Tanzu Brand's guidance, and fix the contradicting
  brief lines.

Each phase becomes its own spec and plan when it starts; the two already written belong to
Phase 1.
