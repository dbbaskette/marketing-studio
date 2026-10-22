# Phase 5: the companions, fully used: design

**Date:** 2026-10-22, at main 21a216e. **Owner's words:** "write the spec for phase
2,3,4,5. Then write the implementation plan for each."

This is Phase 5 of the plan in `2026-10-21-authoring-workflow-review.md`. It is built
after Phases 2, 3 and 4 are merged, so places are named by file and function; line
numbers are at 21a216e and will move.

The companions were read at the versions the suite pins or meets:

| Companion | Version read | Where |
| --- | --- | --- |
| Harness Slides | 0.16.0, commit 1aaab3a | `~/Projects/harness-slides-skill`, the pinned commit |
| Harness Research | 1.0.0, commit 0d7092db (read with `git show`) | the local checkout is 1.0.1-alpha.1; nothing here relies on it |
| Tanzu Brand | 0.14.0, commit 2523280 | `~/Projects/tanzu-brand` |

## What is already true

The review was written at 58e23d5. Some of what it found has since been fixed, and
Phase 5 does not do it again:

- **Presentation Studio asks once whether a deck is a talk or a handout.**
  `runner/decks.py:130-137` takes the form's `delivery` and defaults to `live` for a
  deck from an idea or a brief (`DELIVERY_BY_ROUTE`). `steps/build.py:684 delivery()`
  carries it to the brand export, the look samples and the outline. Only Training Studio
  still hard-codes `reading`.
- **The research brief reaches the writers.** Presentation's outline job gets "Reviewed
  research brief" (`steps/outline.py:371`). Training's `pipeline.findings_text` puts
  `research/brief.md` first under schema 2 (`pipeline.py:1340-1345`). Blog's
  `research_bundle` carries `brief` (`blog_runner.py:1529-1535`). What is missing is a
  sentence that tells the writer what the bundle is (item 9).
- **The slides tool states the code-span rule itself.** In 0.16.0 the outline contract
  (`scripts/lib/outline.mjs:30`) and the compose contract (`scripts/lib/compose.mjs:102`)
  both say it, and `outline check` reports `unmarked-code` with a sentence a worker can
  act on. The studios' own briefs still never mention code spans, and some of their lines
  read as if words must be plain (item 4).
- **The brand's readiness check is wrapped.** Both deck studios' `runner/brand.py` have
  `Brand.ready()`, which runs `doctor --profile presentation --json`. Nothing calls it
  (item 13).

## What is wrong now

1. **Three floors for one tool.** `pins/companions.json` pins Harness Slides 0.16.0 but
   requires `>=0.14.1`; the root `README.md:43` repeats `>=0.14.1`. Both
   `runner/slides.py` files have `MINIMUM = '0.13.1'`. Training's `RELEASE = '0.15.1'`
   (`studios/training/runner/slides.py:187`) is what the page tells a person to update to.
   Tanzu Brand's own installer pins Harness Slides 0.15.1
   (`tanzu-brand/scripts/lib/harness-install-sources.json:6`), so a computer where the
   brand was installed first keeps 0.15.1. Training's `NAMES` has no plain name for eleven
   of the 28 capabilities 0.16.0 lists, among them `compose-code-spans`,
   `google-preview-pool` and `compose-split-point`.
2. **The brand skill has no floor.** Both deck studios call `look samples`, `look choose`,
   `contract export --delivery` and `guidance start --brand`. Tanzu Brand 0.14.0 has all
   of them. An older brand skill fails at the step that needs one, in the brand's words.
3. **A dead path waits for a capability that does not exist.** Presentation's
   `slides.py:463-467` asks for `--events` when the tool lists `progress-events`. Harness
   Slides 0.16.0 does not list it (`scripts/lib/runtime-version.mjs:7`) and has no
   `--events` option. `slides.progress`, `PROGRESS`, `runner/slide_events.py` and the
   observer in `worker_tools.py:751` never run.
4. **No studio brief mentions code spans.** `briefs/outline-*.md` and `briefs/section.md`
   (Presentation), `briefs/deck-outline.md`, `deck-section.md` and `deck-section-design.md`
   (Training) say nothing of backticks. The workers get the rule only deep inside the
   contract text.
5. **Training decks are always for reading.** `runner/deck.py:94` has
   `DELIVERY = 'reading'    # a deck is read alone as well as presented`. Line 372 refuses
   any other: "This deck is read alone as well as presented: set `delivery` to
   "reading"". `engine.py:1575` and `1644` export the brand for reading. Tanzu Brand's
   `references/slide-training.md:4` says "A spoken session implies live; independent study
   implies reading", and `presentation-application.md:23` says to ask once.
6. **The critic's questions are copied, and have drifted.** `steps/build.py:103` and
   Training's `deck.py:148` each hold `QUESTIONS`. The tool's own
   (`compose-preview.mjs:105`) differ in three: "on the element that carries the point",
   "every element", "every image and icon". Presentation's docstring (build.py:73) says
   "The tool's own are not handed to a caller". They are: every whole-deck preview writes
   them into `critic.json` as `questions`.
7. **The brand audit runs last.** Presentation's `steps/build.py:1674 render()` audits the
   deck after review and repair; Training's `engine.py:2581` does the same. A blocker the
   audit finds lands on the person at the deck stop, after the repair rounds that could
   have fixed it.
8. **The reviewer reads only the eight questions.** Presentation's `review_work`
   (build.py:1509) and Training's `pipeline.review_work` give the reviewer "the review"
   (`asked()`) and nothing else. Harness Slides' `references/review.md` (in the snapshot as
   "review guidance", `core/studio_core/brand_guidance.py` `GUIDES`) and the brand's
   checklist (Tanzu Brand `references/slide-review.md`, "Use the Brand checklist") never
   reach it.
9. **The writer is not told what the research bundle is.** Blog's `blog_worker.POLICY`
   names no `research_bundle`; the writer sees IDs and digests with no instruction and
   repeats them. Training's handoff says "Cite stable finding IDs", which suits the
   blueprint but is read by the learner-guide writer too.
10. **Comparisons are never asked for.** Each studio's research `task['purpose']`
    (Presentation `research_steps.py:262`, Training `engine.py:3269`, Blog
    `synthesis_research.py:193`) names its own priorities and never asks for a comparison,
    so a goal such as "Redis or Valkey for session caching" never gets the
    criterion-aligned table that Harness Research's `synthesize.md` builds when asked.
11. **Presentation decks cannot carry a picture.** `runner/slides.py:630-676` wraps
    `assets status|check|icon|add-supplied` and `images generate`; nothing calls them, and
    the compose call never passes `--asset-project`.
12. **Previews wait for each other when they need not.** `PREVIEWING = threading.Lock()`
    (both `slides.py`) and `worker_tools.one_at_a_time` (one lock file a computer) let one
    preview run at a time. Sections are drawn three at a time (`engine.AT_ONCE`) and decks
    two at a time (`settings.parallel`). Harness Slides 0.16.0's Google preview pool keeps
    four reusable preview decks by default (`preview-pool.mjs:34`) for exactly this.
    LibreOffice cannot run two renders under one profile, so local renders must stay
    one at a time.
13. **Fonts are never checked.** `slides.ready()` checks soffice, pdftoppm and Drive
    itself. The brand's `doctor --profile presentation` also resolves Arial
    (`tanzu-brand/scripts/lib/readiness.mjs:55-57`) and is never run.
14. **Blog's brand handoff never passes the voice.** `references/brand-handoff.md:19-21`
    says to pass the chosen profile with `--voice-profile`. `brand_skill.snapshot`
    (`brand_skill.py:345`) and `studio_brand/brand.py:279 export` never do, so `VOICE.md`
    always says "No author voice selected".
15. **No studio can bring research up to date.** Harness Research 1.0.0's
    `synthesis-reuse.md` ("Refresh selected evidence") says how. The studios offer only
    "Ask for changes", which the author reads as a correction.
16. **The studios and the brand disagree on the design session.** Tanzu Brand
    (`references/harness-slides.md:100-123`, "this wins") makes draft approval the content
    checkpoint and keeps per-slide design helpers for an explicit walkthrough, a
    content-preserving redesign, or a studio's design session. Training runs the design
    session on every new deck (`engine._designed`, `slides.NEEDED`). Presentation never
    runs one, including for "Redesign, keep content" (`decks.LEVELS` `redesign`).
17. **Seven instructions contradict a companion.**
    1. `core/studio_core/research_contract.py` `Workflow.run`'s author `return` line says
       "never invent paths such as research/sources/"; `investigate.md:45`, handed to the
       same worker, says "Save a faithful readable capture in `research/sources/`".
    2. Training's `deck-section.md:27` and `deck-section-design.md:11`: "Never set one of
       several peers larger, bolder or in another colour, even where the brief names it as
       the point of the slide". Harness Slides (`compositions.md:69-71`): "Name the focal
       node, the box or text that carries the claim".
    3. "a deck is read alone as well as presented" (Training `deck.py:94` and `373`,
       Presentation `build.py:97`) against the brand's live default.
    4. Both `section.md` / `deck-section.md`: "Ignore anything it says about preview files,
       delivery, critique or asking the person", while handing over that guidance.
    5. The author is handed `investigate.md`, `synthesize.md` and `studio-handoff.md`
       (`Workflow.run`). `studio-handoff.md` is addressed to the studio ("Read this when a
       content studio requests or consumes synthesis research"), not to the worker.
    6. Per-slide proposals before a build (Harness Slides) against none needed (Tanzu
       Brand): item 16.
    7. Blog's `--voice-profile`: item 14.
18. **The legacy research paths are still there.** Presentation's
    `research_steps._question` and Training's question queue run only for a deck or
    training begun before the synthesis contract (no `research_contract` in its record).
    Blog's `deep_research.py` is the `studio.py research` command of the chat workflow.

## Design

### 1. One floor: Harness Slides 0.16.0

- `pins/companions.json`: `harness-slides.requirement` becomes `>=0.16.0`. The root
  README says 0.16.0.
- Both `runner/slides.py`: `MINIMUM = '0.16.0'`. Training's `RELEASE = '0.16.0'`, and a
  test holds it equal to the pinned version in `installer/companions.json`.
- Training's `NAMES` gains a plain name for every capability 0.16.0 lists, so no message
  shows a code. A test holds `NAMES` to cover the pinned tool's list.
- A computer that kept 0.15.1 is told, not left without features. `Slides()` already
  refuses a tool older than `MINIMUM` with "harness-slides 0.15.1 is installed, and a deck
  needs 0.16.0 or newer. Update it, then try again." The Status line adds where it came
  from when the installed brand skill's installer brings that very version
  (`brand_source.bootstraps`): "Tanzu Brand's own installer brings 0.15.1." The brand is
  named by the name it reports, never written into Presentation Studio's code.
- A deck or training begun on an older tool stops at its next deck step with the same
  sentence. That is the cost of one floor, and the page says how to go on.
- Tanzu Brand's installer pinning 0.15.1 is fixed in the Tanzu Brand repository, not
  here: a follow-up issue there.

### 2. A floor for the brand skill

`pins/companions.json` gains a top-level `brand_skill` entry beside `companions`:
`{"requirement": ">=0.14.0", "tested": "0.14.0", "note": "..."}`. It has no repository
or commit, because the brand skill is the person's own and Marketing Studio never
installs it. Both deck studios read the brand skill's `version` once with their check of
this computer. An older one is a Status line: "Your brand skill is 0.13.2. Decks need
0.14.0 or newer, for its look samples and talk-or-handout export. Update it in
Settings." Installers ignore the entry.

### 3. The dead progress-events path goes

Remove `PROGRESS`, `Slides.progress`, the `--events` branch of `Slides.preview`,
`runner/slide_events.py` and the observer in `worker_tools.py`. `build_progress.Preview`
keeps its start and finish records, so the page still shows that a preview is running and
when it is done.

### 4. Code spans, said by the studio

One line goes in every brief that writes or draws slide words: Presentation's
`outline-brief.md`, `outline-material.md`, `outline-spec.md` and `section.md`; Training's
`deck-outline.md`, `deck-section.md` and `deck-section-design.md`:

> Write a configuration field, command, API or file name as a code span in backticks,
> such as `` `highAvailability` ``, with plain English first the time it appears. A title
> names things in words and takes no code span.

The studios' own word checks (`kept`, `WORD`) already treat backticks as punctuation; a
test pins that a point with a code span is kept and counted the same as without.

### 5. Training asks once: a talk or a handout

- The deck step of Training's form asks "How is this deck used?": **Presented in a
  session** (`live`, the default) or **Read on its own** (`reading`). It is asked once a
  training, and the page states the default.
- `pipeline` keeps it in the session as `delivery`. `deck.DELIVERY` stays only as the
  value for a training saved before this field: those stay `reading`, as they began.
- The outline check, the brand export (`engine.py` 1575 and 1644) and the look samples
  read the training's delivery. The refusal says "This deck is presented in a session:
  set `delivery` to "live"." or "This deck is read on its own: set `delivery` to
  "reading"."
- A live deck's outline gets the slides tool's `no-notes` findings, and the outline brief
  says what live notes carry ("what the presenter says, and the source behind the
  claim").
- A state-transition matrix row: a training with no `delivery` reads as `reading`; a new
  one defaults to `live`; changing it after the first outline is refused ("The deck has
  been written for <delivery>. Start the deck again to change it.").

### 6. The critic's questions come from `critic.json`

A new shared module, `core/studio_core/critic.py`, reads the questions from a whole-deck
preview folder: `questions(folder) -> tuple[str, ...]`, refusing a missing or malformed
`critic.json` with "The slides tool's review questions are not with this preview. Put
the deck together again." Each round records the questions it was reviewed with. The
reviewer's `asked()`, the findings check and the reuse check read the round's own, so a
tool update cannot leave a round checked against questions it was not asked. Both
`QUESTIONS` constants and the docstring sentence go.

### 7. The brand audit before review

After a round's whole preview and before its review, the studio runs the brand's audit
over that round's previewed deck. Each blocker on a slide becomes a `critical`
`drawing` finding for that slide's section, with the audit's own words. The repair rounds
draw those sections again within `REPAIRS`, as for a reviewer's finding. Warnings go to
the reviewer as notes to look at. `render()` still audits the delivered deck, and the
gate still shows that result. A brand skill that cannot audit leaves the round as it is,
with the note it has today.

### 8. The reviewer gets the review guidance and the brand checklist

The reviewer's job inputs add "review guidance" from the brand's guidance snapshot (or
`slides.reading()`), and the brand's review checklist when the brand's `guidance start`
answer names one (`brand.review`, the path Tanzu Brand gives to its `references/slide-review.md`, read as `brand_texts` reads Markdown files:
an absolute path to a regular `.md` file, up to `READ_MOST`). The review brief says to
read both and to judge by the eight questions.

### 9. What the research bundle is, told once

A shared sentence, `research_contract.HANDOFF`, goes to every writer that receives
research:

> The research is reviewed. Read its brief first: it says what matters for this piece.
> Use the facts and findings to check what you write. Their IDs, digests and verdicts
> are for checking and for provenance, notes and source lines: never put one in the
> words a reader reads.

Blog's `POLICY` names `research_bundle` and carries the sentence. Training's
`findings_text` and Presentation's outline inputs carry it in place of their current
lead lines. Training keeps "Cite finding IDs" only in the blueprint and brief briefs,
whose formats need them.

### 10. Comparisons when the goal compares

`research_contract.purpose(kind, goal, priorities)` builds the purpose line all three
studios now build by hand. When the goal compares options (it names "compare",
"comparison", "versus", "vs", "or" between two named options, "alternatives", "choose
between", "which is better"), it adds: "The goal compares options: include a comparison
with one criterion per row, and say where something is unknown rather than absent." A
word-list match is predictable and tested; it can be wrong both ways, and costs only one
sentence when it is.

### 11. Supplied pictures on Presentation decks

- On the outline gate, a person may add a picture to a cover, section or concept slide:
  a PNG or JPEG, its alt text, and where it came from. It is recorded with
  `assets add-supplied` into the deck's asset project, and the slide's outline entry
  names it by asset ID.
- The composer is told which slides carry a picture and draws it by `asset`. Build
  compiles with `--asset-project`. `asset_check` runs before the deck stop; its problems
  are shown in its own words.
- Generated images are not offered: see Out of scope.

### 12. Previews in parallel through the pool

- `slides.py` replaces the one `PREVIEWING` lock with a turn per renderer: local renders
  stay one at a time; Google renders on a tool with `google-preview-pool` take one of
  `HARNESS_PREVIEW_POOL_SIZE` (default 4) turns, a `threading.BoundedSemaphore`.
- `worker_tools.one_at_a_time` becomes `turn(lock, slots)`: slots lock files beside the
  one there is now, taken first free. Local is one slot; pooled Google is the pool size.
  A turn left by a process that ended is taken, as now.
- The deck's remembered Drive file is not named on a pooled tool already
  (`named = ... not self.has('google-preview-pool')`), so turns cannot fight over one file.

### 13. The brand's doctor in Status

The check of this computer runs `Brand.ready()` once with its other looks (cached as they
are). It shows the doctor's `arial` capability: available, or "Arial was not found on
this computer, so slides may be drawn in another font. Install licensed Arial." Where the
doctor reports the same programs `slides.ready()` checks, Status shows one line for each,
not two. `slides.ready()` keeps its own checks for a brand skill without `doctor`.

### 14. Blog passes the chosen voice to the brand

`brand_skill.snapshot(brand_id, variant, voice=None)` takes the run's pinned voice and
writes `{id, revision, guide, status}` from the pinned profile revision to a file in its
temporary folder, passed as `--voice-profile`. `studio_brand.brand.Brand.export` takes
`voice_profile: Path | None`. A tone-only or preserve run passes none. The brand's
refusal of a profile without a guide is shown as it is.

### 15. Bring the research up to date

Where a person asks for changes to approved research, the sheet offers **Bring the
evidence up to date** (with "Re-reads the sources and checks the report again: about as
long and as costly as the research was"). It sets `task['refresh'] = True`. The author is
then handed `synthesis-reuse.md`'s "Refresh selected evidence" section with its stage
references, and its `return` line asks it to save new captures with access dates. The
review that follows is the whole review, as Harness Research 1.0.0 requires. The cost
sentence is Phase 3's price of revising the research, where Phase 3 shows one.

### 16. The design session: the brand's checkpoints win

- **Training:** a new deck is approved on its outline and its look, as the brand says,
  with no design session. The form's deck step offers "Walk through each slide's design
  before it is built" (off). A deck with it on runs the design session as today.
  `engine._designed` returns the form's choice for a new deck; a deck already written
  keeps what it was written with. `slides.NEEDED` keeps only what a deck without a design
  needs, and the design capabilities are needed only when the walkthrough is on.
- **Presentation:** "Redesign, keep content" has no design session. The decision,
  written into `docs/runner.md` and `references/levels.md`: the extracted outline is
  approved at the outline stop, the look is chosen from rendered samples, and per-slide
  changes are asked for at the deck stop by marking slides. The brand's "content-preserving
  redesigns use a per-slide walkthrough" is named as not followed, and why: Presentation
  has no design gate, and porting Training's is its own project.
- The brand's `references/harness-slides.md:121` says "inside Presentation Studio's design
  session"; it is Training Studio's. Follow-up issue in the Tanzu Brand repository.

### 17. The contradicting lines, put right

1. The author's `return` line: "The studio's tools have saved every capture for you:
   that is the capture `investigate.md` asks for. Cite each source by the file path the
   tools gave it, exactly. Write no files yourself." The `research/sources/` clause goes.
2. Training's section briefs: "Equals share one size and weight. Where the outline names a
   focal, give it the one emphasis on the slide, as the composition guidance says. On a
   slide that compares equals (`contrast` or `parallel`), set them alike." The "even
   where the brief names it" clause goes.
3. "read alone as well as presented" goes from every line (items 5 and 1).
4. Both section briefs: "Your reading speaks of previews, critique, delivery and asking
   the person. Here: preview with `preview_section`; a separate reviewer answers the
   critic's questions after you, so write no critique; delivery and questions to the
   person are the studio's, and you cannot ask."
5. The author is handed `investigate.md` and `synthesize.md` only.
   `studio-handoff.md` is read by the studio's code and docs, not the worker.
6. Item 16.
7. Item 14.

### 18. The legacy research paths stay, and say why

The question queue in Presentation and Training is kept: a deck or training begun before
the synthesis contract still finishes on it, and the working agreements say to preserve
existing work. Each studio's `docs/runner.md` says so in one sentence, and that it can go
once no workspace holds such a run. Blog's `deep_research.py` is kept as the chat
workflow's `research` command; `references/modules/blog-deep-research.md` says plainly
that the page uses Harness Research and the command is for chat. If Phase 3 has removed
either path, this item only checks that the docs agree.

## Out of scope, and why

- **Generated images.** Harness Slides' image provider "is unverified: built from Google's
  documentation and tested against stubs, never the live API" (`references/images.md`),
  needs a Google key the person sets up, costs about $0.05 an image, and is only for
  artwork approved in a design walkthrough. Item 11 does supplied pictures only.
- **PDF export completeness for Training handouts.** Training delivers PowerPoint, Word
  and Google files, no PDF, and `delivery inspect` takes a deck scene, which the studios
  do not write. It belongs with a PDF delivery, when there is one.
- **The brand audit's `--exceptions`.** An exceptions file is bound to one deck's SHA-256
  and each entry needs a person's reason. Writing one automatically would be the studio
  excusing its own warnings.
- **`look samples --slide`.** The brand already picks "the first content slide with a
  point to mark and a relation to draw" (`scripts/look.mjs:37`). Naming the sampled slide
  at the look stop is a page wording change, in Phase 2's copy fixes or Phase 4.
- **A design stop for Presentation's redesign.** Item 16 records the decision instead.
- **`synthesis validate`** in place of the throwaway-case `save`. It needs Harness
  Research 1.0.1, which is not released.
- **Removing the probes for a slides tool that lists no capabilities** (`designs()`,
  `sections()`, `assets()` asking by a refusal). After the 0.16.0 floor they are
  unreachable. Taking them out touches every stand-in and many tests for no change a person
  sees; it is cleanup for later.
- **Removing the legacy research paths.** Item 18.
- **Tanzu Brand's own installer pin and its design-session wording.** In the Tanzu Brand
  repository; follow-up issues there.

## Testing

All tests use disposable folders, settings, Git identities and the existing stand-ins;
no provider job runs and no image is generated.

- Root: `tests/test_companion_versions.py` (the 0.16.0 requirement and the
  `brand_skill` entry ignored by installers), a new `tests/test_critic.py`, and
  `tests/test_research_contract.py` (the purpose builder, the handoff sentence, the author
  guide and return line, refresh).
- Presentation: `test_runner_slides.py` (floor, no events, turns), `test_build_progress.py`,
  `test_step_build.py` (questions from the round, audit before review, asset project),
  `test_briefs.py` (code spans, section lines), `test_step_outline.py` (pictures,
  handoff), `test_runner_brand.py` (doctor, brand floor), `test_engine.py`,
  `test_no_brand_named.py`, `test_desk.py` for the page.
- Training: `test_runner_slides.py`, `test_runner_deck.py` and `test_runner_deck_whole.py`
  (delivery, questions, audit, design opt-in), `test_workspace.py` (the matrix row),
  `test_runner_engine.py`, `test_runner_brand.py`, `test_desk.py`, and
  `validate_package.py` for guidance budgets.
- Blog: `test_blog_runner.py` and the brand tests for `--voice-profile`; the worker
  policy test for the handoff sentence; `scripts/measure_guidance.py --check`.
- Full: each studio's `scripts/ci/run_tests.py`, the root suite, and
  `bash scripts/ci/tart-macos.sh` once before the pull request.
