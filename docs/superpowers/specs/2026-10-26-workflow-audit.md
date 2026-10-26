# The workflow after the writing desk: audit and the order of work

**Date:** 2026-10-26, at main cc53056. **Owner's words:** "Lets apply our UI changes to blog
studio to the other studios. We also need to do an audit of workflow and clean it up", and,
asked whether that meant the layout rules or the writing desk as well: "1 and 2".

Three read-only audits fed this document, one per studio, with Marketing Studio's home and
shared setup in Blog Studio's. Their full findings, with file and line references and the
page's own words, are beside this file:

- [Presentation Studio](2026-10-26-workflow-audit/presentation.md)
- [Training Studio](2026-10-26-workflow-audit/training.md)
- [Blog Studio, Marketing Studio home and shared setup](2026-10-26-workflow-audit/blog-and-shared.md)

## What the audits found

### Broken paths that cost a person work

- **Presentation Studio.** Balanced never shows the look choice for "Redesign, keep
  content": the deck is drawn in the brand's default look and the record calls it
  "Automatic draft". A PowerPoint deck in a team workspace can be downloaded only on the
  computer that made it. No test walks any route at Balanced or Automatic.
- **Training Studio.** A teammate's edits in a Google Doc almost never come back: the pull
  is offered only after a push fails. No source can be added once research is planned. One
  change at the final review reopens the first review and redraws every slide. Downloads
  from the final review have no file extension.
- **Blog Studio's desk.** A teammate cannot take over a desk blog; a stopped start can only
  Retry; a desk blog can never get a Google Doc; restoring a deleted desk blog dead-ends;
  the Proofread panel describes Apply a voice; desk blogs never reach the team library.

### Copy that says what the page does not do

About ten sentences in Presentation Studio describe Step by step although new decks start
at Balanced; Training Studio's review-level card contradicts itself; "desk" means the whole
page in all three studios and also Blog's new writing screen. Each studio has a dozen names
for asking for a change.

### Cleanup

- **The two deck studios carry a hand-kept fork of one runner**, already drifting
  (agents, brand, team, gitstate, documents, slides, upkeep, worker tools, settings).
- **Blog Studio's old flow is still live for chat.** Chat's `run create` makes gated runs;
  until chat starts desk blogs, the pipeline, review levels, claims map and research stop
  serve new work, not only older blogs.
- **Safe to delete now:** Blog's old Polish and Google intake screens, the page's
  `run-create` route and its form-only fields, unused page code and CSS, Presentation's
  rehearsal placeholder bead, dead helpers in core.
- **After a scan of saved work:** the legacy research question queue (new decks and
  trainings can still land in it when the research helper lacks synthesis), the cover
  sample for brand skills without looks, review layout 1, pre-0.16 Harness Slides branches.
- **Docs:** stale lines in every README and runner guide, the retired `training-studio`
  repository still linked, specs still called "the full specification".

### Layout rules

Presentation Studio and Training Studio miss most of the layout rules in
`docs/design/golden-gate.md`: more than one filled button per screen, no ledes, what needs
the person below work in progress, full-page wizards instead of numbered sheets, no filter
rows, controls under 44px. Marketing Studio's setup has three titles for one step, two
saves, and a page stylesheet that draws shared controls. The components the rules name
(filter row, selection bar, numbered sheet steps) live only in Blog's `blog.css`.

### The desk elsewhere

Most of a deck desk exists already: a note on one slide redraws only its section, notes are
taken while a deck builds, unchanged sections are reused after an outline edit, slides
appear as they are drawn, repair rounds need no person and only changed slides are reviewed
again. What is missing is a way to reach these without a stop, per-slide history, speaker
notes as their own edit, and selection edits that patch the text. A slide note is minutes,
not seconds: it redraws, renders and runs the brand check.

A training desk reuses Automatic draft's acceptance with no stop, Training's
content-addressed history, the in-process checks and per-slide outline data. It needs
section jobs for the guide and brief, a change to the guide that holds the deck and
scenarios built from it until the person updates them, and a scoped deck redraw.

Both audits say the same thing first: share the parts before building either desk. Blog's
version store, the per-part stale check, the "a job lands only if its part is unchanged"
rule, History with compare and restore, selection edits, Finishing preview and apply, the
progress line, Proofread and the desk styles can move to `core/studio_core` and `ui-kit`.
The job queues stay per studio; only the settle rule is shared.

## The order of work

Each piece gets its own spec and plan, an issue, and a pull request merged before the next
starts. The desk specs (5 and 6) are shown to the owner before they are built.

1. **Workflow fixes.** The broken paths and wrong copy above, in all three studios and
   Marketing Studio's setup, with route tests at every review level.
2. **Cleanup.** What is safe to delete now, the stale docs, and the shared runner: the
   modules the deck studios copy move into `core/studio_core` with the product name passed
   in, as `server.py` and `studios_config.py` already are.
3. **The shared desk.** Blog's desk parts move into core and `ui-kit` under a name that is
   not "desk" (Training Studio's page already uses it), with Blog switched to them and
   nothing a person sees changed.
4. **The layout pass.** The layout rules in Presentation Studio, Training Studio and
   Marketing Studio's home and setup, with the shared components moved out of `blog.css`.
5. **The deck desk** in Presentation Studio.
6. **The training desk** in Training Studio.
7. **Retiring the old flows.** Chat starts desk work; then the gated pipelines, the review
   level controls and the legacy research queue go, once a scan finds no saved work that
   needs them.

## Settled here

- **Names.** People see "the desk" for the editing screen in every studio. In code the
  page modules keep their names; the shared module is `studio_core/drafting` and its page
  kit `ui-kit/drafting.js`.
- **Saved work keeps working.** New work carries `flow: "desk"`; anything without it keeps
  today's pipeline and screens. Finished work offers **Open on the desk**.
- **Review levels.** Once all three studios start new work on desks, the shared level
  governs only saved runs. It stays readable; its controls go in piece 7.
