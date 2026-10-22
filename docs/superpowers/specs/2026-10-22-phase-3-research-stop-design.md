# Phase 3, the research stop worth stopping for: design

**Date:** 2026-10-22, at main 21a216e (after Phase 1, PRs #77 and #79). **Owner's words:**
"write the spec for phase 2,3,4,5. Then write the implementation plan for each."

Phase 3 of `2026-10-21-authoring-workflow-review.md`. Phase 1 made research that can
finish and stops that name their cause. This phase makes the research stop itself worth
the person's time: it shows what the research found and what the check said, it says what
a change costs before it is sent, it keeps research inside the boundary the person chose,
and it runs no planning job where the person's own material is all there is.

Phase 2 (honest copy and one vocabulary) merges first and may rename labels. This spec
names controls by what they do and where they live, not by their label.

## What is wrong now

### The research stop shows a hash, a count and boilerplate

Harness Research 1.0.0 publishes `research/brief.md` (the authored, prioritized handoff),
`research/evidence.md` (facts, quotes, sources, every verdict) and `research/facts.json`,
whose `review` holds the checker's `assessment: {coverage, usefulness, note}`, any
`originals` it could not read, and a verdict per fact, finding and passage. Findings carry
`gaps`; report and brief blocks of kind `gap` say what is not known; a source with
`context: partial` has a `context_note`. No studio shows any of it.

- **Training Studio.** The gate shows the report and, beside it, "No automatic checks
  apply here. It is yours to read." (`skills/training-studio/scripts/desk/app.js:2215`).
  The gate payload carries the file's `sha256` (`desk.py:535`) and the review line reads
  "The report and authored brief were reviewed against saved evidence. Keep all
  qualifications and gaps. Digest: …" (`runner/engine.py:3372-3374`).
- **Presentation Studio.** Under the synthesis contract `_findings_shown`
  (`runner/research_steps.py:178-188`) gives every finding `question: ''` and
  `status: 'supported'`, so the gate reads "N questions · N answered by the sources · 0 to
  look at" (`desk/app.js:3848-3849`) over cards whose question line is empty
  (`desk/app.js:3904`). Under Balanced the direction review replaces the triage cards
  with the raw report: `documentPart('Research findings', gate.research.text)`
  (`desk/app.js:4154`).
- **Blog Studio.** The research stage's notes are a constant: "Independent evidence and
  prose review completed for the saved research digest. The authored brief, evidence,
  source limitations and digest are retained in research/." (`synthesis_research.py:337-339`),
  shown under "Worth a look" (`assets/management/runner.js:252`). "Checked for you" holds
  two rows that are always true (`blog_runner.py:2349-2356`).

### The plan stage speaks the old queue's language

Both deck studios' plan briefs (`runner/briefs/research-plan.md:30-31` in each) say "Ask at
most 30 questions" and "Each question is researched on its own, which costs the person
time and money". Under the synthesis contract one author investigates once and one checker
reviews; the plan's items arrive only as `planning_questions` (`research_steps.py:266`,
`training/runner/engine.py:3275`), and nothing maps a finding back to the question it
answers. `worker_tools.QUESTIONS = 30` (`presentation/runner/worker_tools.py:130`).

Blog Studio's research-plan job is a tool-less writing job handed
`modules/blog-deep-research.md` (`blog_runner.py:71`), a module written for a conversation
with browsing tools ("Use available browsing/search tools to investigate one question at a
time", line 93). It returns a hint the synthesis author receives as `planning_document`
(`synthesis_research.py:200`). That module also documents two research systems side by
side: "New synthesis research" (line 10) and the legacy `deep_research.py` commands from
"Research in the existing harness" (line 91) on.

### A change to the research is the most expensive request, and it is priced nowhere

Asking for changes at a research stop runs the author and the check again, up to three
rounds, and then makes again everything drawn from the research. No sheet says so.

- Training: a request on `research` marks every question to go again
  (`runner/engine.py:3457-3459`); every blueprint, guide, brief and deck direction is built
  from research (`workspace.artifact`, `upstream` includes `'research'`) and is made again.
  The request sheet says only "Your assistant makes the change and brings it back here."
  (`desk/app.js`, `FORMS.revise`).
- Presentation: per finding, "Research again" (`desk/app.js:3928`) reads as targeted, but
  under the contract the whole request goes to the author as `requested_changes`
  (`research_steps.py:268`) and every round runs again. The direction review's
  "Request changes to the research" (`desk/app.js:4166-4169`) also redraws the outline and
  the looks. Only a stopped research says what rounds took (`engine.py:2605-2615`,
  `desk/app.js:3518-3531`).
- Blog: "Ask for changes" naming the research stage reruns the rounds and every later
  stage; only Try again after a stop is priced (`runner.js:61`).

The Training stop card names `reviews/research.md` and has no button to open it
(`runner/engine.py:3197-3201`); Presentation has "Read every objection" since Phase 1.

### Research ignores the boundary, or claims one it does not keep

- **Presentation Studio has no boundary.** The form has one chip, "Research it first"
  (`desk/app.js:2873`). The plan job is always told "the public web" and its artifact is
  always `'scope': 'public-web'` (`research_steps.py:479-498`), so a confidential document
  with research on produces public queries built from it.
- **Blog Studio ignores its own setting.** Settings → Research is saved
  (`runner.js:161`), but every Home card sets `studio.draft.research='none'`
  (`runner.js:165`), and the start screen's "Ready to start" card says "Research uses only
  the sources you allow." whenever research is not `none` (`runner.js:179`), including when
  no source is ticked and `research_scope` (`blog_runner.py:913-915`) runs none.
- Training Studio already asks (`pipeline.SOURCES`: "Public web", "Your documents only",
  "The public web and your documents") and honours it in the plan job
  (`pipeline.py:1281-1301`) and the task (`engine.py:3277`).

### A planning job where the person's material is all there is

With supplied-only research every studio still pays for a plan job. In the deck studios it
drafts up to thirty questions about documents the person chose. In Blog Studio, supplied
facts and material go through the full synthesis author and check, which is what produced
the announcement's "not confirmed by the supplied evidence" hedges
(`studios/blog/docs/superpowers/specs/2026-10-21-announcement-writing-design.md`, "A
research stage that added only doubt").

## Design

### 1. One account of the research, from the bundle

A new shared module, `core/studio_core/research_view.py`, reads a published bundle with
`research_contract.read_bundle` and returns what every research stop shows, so the three
studios say the same things in the same words:

- **The brief** (`brief.md`) first, as the main reading surface, opaque, rendered as
  Markdown. It is the research's own prioritized handoff.
- **What the independent check said**: one sentence ("The independent check accepted the
  report and the brief: it found their coverage honest and the brief fit for its use."),
  then the checker's own note, then any original it could not read with its access error.
- **What the research could not settle**: every finding gap and every `gap` block of the
  report and brief, each once, in order; then each source read only in part with its note.
- **What it read**: "12 sources: 3 of yours, 9 public."
- **Your questions**: each planning question with the findings that answer it, or "The
  research did not answer this." Findings that answer no planning question follow under
  "Also found".
- The report and the evidence are folded beneath, each as its full text.

No digest and no hash is shown anywhere. Training's review line becomes the check's
sentence and note; its gate payload drops `sha256` from what the page renders (the field
stays for decisions that bind to a version).

**Findings mapped to questions.** The core tells the author, whenever the task carries
planning questions: "Planning questions have IDs. A finding that answers one has an ID that
begins with that question's ID and two hyphens, such as instance-min--capacity. Keep each
ID within 64 characters." This is a naming convention inside Harness Research's ID rule
(`^[a-z0-9][a-z0-9-]{0,63}$`), not a new field, so the dossier schema is untouched. The
studio maps a finding to the question whose ID it equals or begins with, followed by
`--`; the longest match wins. A finding that follows no question is "Also found".

### 2. The plan brief for one investigation

Each deck studio keeps today's brief, unchanged, as `research-plan-queue.md` for runs
without the research contract. `research-plan.md` is rewritten for the synthesis path:
the questions say what the deck or training must be able to say; one investigation answers
them together and an independent check reviews it; at most **8** questions; no sentence
about each question being researched on its own. A contract run's plan artifact is
checked against 8 (`'most': 8` in the artifact spec); a legacy run's against 30.
Presentation records the change in `vendor.json`.

Blog Studio's research-plan job gets a module of its own, `modules/blog-research-plan.md`,
written for a tool-less worker: at most 8 questions, one a line, as
`- **<id>**: <question>`. The runner reads them into `planning_questions` for the
synthesis author, so the mapping above works in Blog Studio too.

`modules/blog-deep-research.md` documents only the synthesis path. The legacy commands
move to `modules/blog-legacy-research.md`, which the main module names in one line: load it
only for a blog whose research was saved before synthesis. Existing legacy research still
continues; nothing is converted.

### 3. Every research change priced before it is sent

Each research stop's payload carries `research_price`: the last try's rounds, jobs,
seconds and dollars (from `research_contract.last_rounds`), the rounds a change may run,
and the labels of the made things the change will make again. `research_view` words it
once:

> Asking for changes runs the research again from its last report: up to 3 rounds of
> writing and checking. Its last try took 48 minutes and $9.80. Then it makes again: every
> blueprint, the learner guides, the reference briefs and the deck outlines.

With nothing recorded: "No time or money was recorded for its last try." The sentence
sits in the request sheet of every research stop, above the send button, and in the
Balanced direction review's research request in Presentation Studio. If Phase 2 has added
a general price line to request sheets, the research stop shows this sentence in its place.

What it makes again:

- Training: every made artifact downstream of `research` in `workspace.artifact`'s
  `upstream` graph (a new `workspace.downstream`).
- Presentation: the steps `_reopened(record, 'gate:research')` names that are done.
- Blog: the stages after `research` in the run's pipeline that have a saved version.

**Presentation's per-finding control is honest.** Under the contract, the per-finding
control asks about that finding ("Ask about this finding", with a line saying what is
wrong). Its note travels in the one request, and the sheet carries the sentence above:
the whole research runs again. The legacy path, where a question really is researched on
its own, keeps "Research again".

**Training's research stop opens its objections.** A stop that kept objections shows
"Read every objection", which opens `reviews/research.md` through the page's file view,
as Presentation Studio does.

### 4. Triage at the direction review (Presentation Studio, Balanced)

Under Balanced the direction review shows the account of design item 1 in place of the
raw report, with each finding's "Leave out" control. Leaving findings out at the
direction review sends `direction_target: 'gate:research'` with
`marks: {left_out: [...]}` and no note. That is not a research change: the runner records
the findings left out and redrafts the outline and the looks without running research
again. The sheet says so, priced from the outline's and looks' last tries. The tally of the
review counts "2 findings left out". A note to the research, as today, is a research change
priced as in item 3.

### 5. A research boundary on every start form, kept

- **Presentation Studio.** With research on and a document route, a second choice: "Where
  may research look?" with "Your documents only" (the default) and "Your documents and the
  public web". It is saved as `form.research_sources` (`'documents'` or `'both'`). Your
  documents only gives the plan job the supplied-only instruction and no search words, the
  plan artifact `scope: 'supplied-only'`, and the task `source_mode: 'selected'`. The
  scratch route, which has no documents, says research uses the public web. A deck started
  before this keeps what it had.
- **Blog Studio.** A Home card starts with the research default from Settings, except
  Explore ideas, Revise and Review, which start with none, and Polish a document, which
  has its own editor control. "Ready to start" says what will happen, from the stages the
  run will have: no research; research that reads only the N ticked sources; research that
  reads the ticked sources and the public web; or "No research: no source is ticked." Phase
  2 owns the control's words; this item owns what it does.
- **Training Studio** already asks and keeps the boundary. Only its plan job changes
  (item 6).

### 6. No planning job where the material is all there is

- **Deck studios, supplied-only research.** When research may read only the person's
  documents (Training `source_scope: 'supplied-only'`; Presentation
  `research_sources: 'documents'`) on a contract run, no plan job runs. The studio writes
  the plan itself from an optional field on the form, "What should the research answer?
  (optional)": one question a line, at most 8 lines of 300 characters. With none, one
  question: "What do the supplied documents say that serves this goal: <goal>?" Training
  accepts that plan under the run's saved review policy (`workspace.accept_policy`) under
  Balanced and Automatic, so Balanced's first stop becomes the direction review; Step by
  step still stops at the plan, now free. Presentation's plan gate keeps its present
  policy behaviour. The timeline row reads "Research plan: written from your form".
  Training adds state-transition matrix row 119 and its test.
- **Deck studios, web research.** The plan job still runs with the new brief (item 2), and
  the person's own questions are handed to it to keep, in their words.
- **Blog Studio, supplied-only research.** When a run would research only ticked
  supplied sources, the research-plan and research stages are replaced by one
  **claims-map** stage: a tool-less job that lists each claim the material makes, with the
  source ID and the exact passage, and judges none. The runner checks every passage against
  the source's text (whitespace-normalized) and gives the job one correction. Later stages
  receive the map with the other earlier stage files; the worker policy says to state those
  claims as the material does and add none it does not make. It is not a writing stage, so
  Balanced and Automatic continue past it; Step by step stops. "Continue without research"
  drops it with the research stages. The from-files path, which reads the files at every
  step and runs no research for supplied-only, is unchanged. This is Task 5 of
  `studios/blog/docs/superpowers/plans/2026-10-21-announcement-writing.md`; that plan's
  other tasks stay with it. Until its messaging role exists, the claims map reads facts and
  material; the messaging role joins them when it lands.

## Out of scope, and where it lives

- Phase 4: downloads, Home cards, applying the review, requiring the look pick, moving
  Training's guide and brief after the direction stop.
- Phase 5: handing `brief.md` to the writers, `research_bundle` explained to Blog's writer,
  comparisons, refresh research, `context: partial` for excerpts, companion version floors,
  deleting the legacy question queue (`research-plan-queue.md` and the per-question path
  stay until then).
- Phase 2: every label and the one research control's words; the general price line on
  request sheets; stop counts. Phase 3 changes what stops exist for supplied-only
  Training runs under Balanced, and Phase 2's stops line must read it from the run.
- The announcement plan's messaging role, notes, qualify-once and Length.

## Testing

All tests use disposable settings, workspaces, Git identities and data folders, scripted
workers and synthetic bundles; no provider job runs.

- Core: the account of a synthetic complete bundle (brief, check sentence and note, gaps
  once each, partial sources, counts, questions mapped and "Also found", unread originals);
  None for a missing or draft bundle; the author payload's ID sentence with and without
  planning questions; the price words with and without recorded cost and with a made-again
  list.
- Presentation: the boundary validated, saved and honoured by the plan job and the task;
  a supplied-only contract run writes its plan with no job; the research gate payload
  carries the account and no digest; findings carry their question; the Balanced direction
  review's leave-out reruns no research and redrafts the outline; the price is in the gate
  payload; the desk journeys (`page_harness.js`) for the panel, the boundary choice, the
  per-finding control and the priced sheet.
- Training: the gate payload's account; the review line with no digest; the plan from the
  form and matrix row 119 under each review level; `workspace.downstream`; the priced
  sheet and "Read every objection" in desk journeys.
- Blog: Home cards take the Settings default; "Ready to start" for each case; the research
  stage view's account and price; the plan module and parsed questions; the claims-map
  pipeline, passage check, correction, Balanced continuation and skip; guidance budgets.
- Each studio's full suite and root `test_ui_consistency` once before completion.
