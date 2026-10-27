# Piece 6: the training desk (Training Studio): design

**Date:** 2026-10-26, at main cc53056. **Owner's words:** "Lets apply our UI changes to blog
studio to the other studios. We also need to do an audit of workflow and clean it up", and,
asked whether that meant the layout rules or the writing desk as well: "1 and 2".

Piece 6 of [the audit and the order of work](2026-10-26-workflow-audit.md). The main input
is section 5 of [the Training Studio findings](2026-10-26-workflow-audit/training.md); every
claim used here was checked again against the code at cc53056, and corrected where the
findings were wrong (see "Corrections to the findings" at the end of "What is wrong now").

The owner reviews this spec before it is built. Pieces 1 to 5 merge first. This piece uses
what piece 3 (the shared desk, `studio_core/drafting` and `ui-kit/drafting.js`) and piece 5
(the deck desk's slide cards) build, and redesigns neither. Their specs were being written
at the same time as this one; where this spec names one of their interfaces it says what it
needs, and the plan's first task maps those needs to the names they finally chose.

Paths: T = `studios/training`, R = `T/runner`, S = `T/skills/training-studio/scripts`,
C = `core/studio_core`.

## Decisions for the owner

Each is a real choice. The recommendation comes first; the design below follows it.

**The owner's answers (2026-10-26):** every recommendation is taken except decision 13. There,
findings become suggestions, as in piece 5 (decision 13 below says what that means here).

1. **The look of a training's decks.** *Recommended:* the brand's default look at Start, and
   **Try another look** on each deck card afterwards (samples first, then a priced redraw).
   *Alternative:* piece 5's start choice, "Pick it when the samples are drawn", which pauses
   the start once per level. A training with three levels would pause three times, so the
   default suits "no stops" better. Either way Training uses piece 5's picker.
2. **Reading the research plan first.** *Recommended:* no stop. The plan is written from the
   form and its questions, and is shown in the Sources panel. *Alternative:* a start option,
   "Let me read the research plan first", which is the one pause a desk start would have.
3. **Research a desk start needs.** *Recommended:* a desk start needs Harness Research with
   synthesis (the research contract). Without it, Start says "Update Harness Research to
   start a training on the desk" and names the Status screen. The legacy question queue is
   never used for desk work, so piece 7 can retire it sooner. *Alternative:* allow the queue,
   and refuse **Add a source** on such trainings.
4. **What happens below a change.** *Recommended:* nothing is rewritten on its own. A card
   built from an older input says so, with **Update from the guide** (priced) or **Keep as it
   is**. *Alternative:* update short text materials (the Yoodli layout, a scenario) on their
   own and hold only the guide, the brief and the deck.
5. **When copies are made.** *Recommended:* Google Docs and Word copies are made when a
   material is marked ready, as today after an approval. **Send to a Google Doc** on any card
   makes or updates its Doc at once, so a teammate can edit a draft in Google.
   *Alternative:* copies only on Mark ready.
6. **Keep as it is.** *Recommended:* the reason is optional, with "Kept on the desk." when
   none is given. It is listed in readiness as today's accepted-as-it-was decisions are.
   *Alternative:* a required reason, as `decide` requires today (S/workspace.py:1056).
7. **What the person marks ready.** *Recommended:* each level's plan and every material on
   it, one card at a time or with **Mark this level ready**. The research and its plan are
   accepted on the desk and count as they do under Automatic draft today. *Alternative:* a
   separate **Mark the research ready** in the Sources panel.
8. **Where a text material's History comes from.** *Recommended:* from Training's
   content-addressed history, read through piece 3's `Versions` interface, with no second
   store. Trainings saved before the desk get History too, and a version is never kept
   twice. *Alternative:* piece 3's part-keyed version files for new edits, plus a reader for
   older history. Slides use piece 5's per-slide store either way, because a slide's words
   live in `deck/outline.json`, which keeps no history of its own.
9. **The whole-guide note.** *Recommended:* one section at a time in order, with progress and
   Stop, as Blog Studio does; a failed section leaves the others done. **Write the whole guide
   again** stays as today's one revise job.
10. **Old finished trainings.** *Recommended:* **Open on the desk** is one way, as in Blog
    Studio: from then on the training opens on the desk, and its review screens are not
    offered again. Its earlier record stays readable in its history.
11. **What Add a source takes.** *Recommended:* documents, in every training. A training
    researched from the public web only reads your documents too from then on, and the sheet
    says so. Links stay out of this piece (save a page as a file).
12. **The name on disk and in code.** *Recommended:* the new Training code uses "drafts"
    (`runner/drafts.py`, `desk/drafts.js`, `/api/drafts/…`), and `docs/desk.md` is renamed
    `docs/page.md`. The `training.py desk` command and `S/desk.py` keep their names, because
    guidance and installed helpers call them. See "Naming".
13. **The deck's review on the desk.** *Decided (the owner, 2026-10-26):* findings are
    suggestions in both studios. Training keeps its automatic review of the slides that
    changed after each slide note or update, so a training's deck never reaches the desk
    unreviewed. No repair round runs. Each finding waits on its slide as a proposal, as in
    piece 5's Review the deck. **Apply** is a slide note made from the finding's note and fix,
    priced. **Skip** keeps the finding as read. The grave-finding rule stands: a deck with a
    grave finding open cannot be marked ready. *Was recommended:* at most two automatic
    repair rounds, as today.

## What is wrong now

### One kind of change, to a whole file

A change to a guide, a brief or a scenario is a request on the whole file. It goes into
`session.requests` and the next worker rewrites the file (R/pipeline.py:1621-1644
`document_work`, which passes the request to `_again`). There is no note on one section, no
selection edit and no typing in place. The request sheet says "Say it in your own words.
Your assistant makes the change and brings it back here." (S/desk/app.js:50), though the
runner has no assistant. Piece 1 fixes that sentence.

### Everything made from a change is made again and stops again

R/pipeline.py:28-31: "Something made from a version of its inputs that has since changed is
made again, and comes back to its gate: a blueprint, a guide, a brief or a Yoodli scenario.
Nothing is ever accepted as it is here." A remade file is a draft again. Its gate under Step
by step, or its combined review under Balanced and Automatic draft, waits for the person
(R/reviews.py:73-122 `group`). In a training with a deck, one edit to the guide makes the
whole deck again.

### A change to a deck redraws every slide

A deck request drafts the deck's outline again (R/pipeline.py:1112-1116). The new start
throws away every drawn section: `self._note(root, level, sections={}, rounds=[], start={…})`
(R/engine.py:2357). Presentation Studio keeps unchanged sections (`_kept`,
`studios/presentation/runner/steps/build.py:1079-1107`); Training Studio does not. The rate
is $0.40 and 1.25 minutes a slide (R/deck.py:99 `RATE`), so an eight-slide deck costs about
$3.20 and ten minutes for a one-word change on one slide. Speaker notes are held to the
outline (`deck.kept`, R/deck.py:1047, a check of each drawn section), so a notes change is a
redraw too.

### No source once research has begun

R/engine.py:3794 refuses any document change once the next step is past adding documents:
"The research for this training was planned from the documents already added, so they
cannot be changed now." (`SETTLED`, R/engine.py:300-301). A forgotten or newer document means
starting the training again.

### History is one comparison

S/desk.py:435-436, `changes`: "A line comparison with the version last approved, when there
is one." Every saved version is already kept by content
(`.training-studio/history/<name>/<sha256><suffix>`, S/workspace.py:487-501), and each save
is an event in `session['events']` with its time and hash (S/workspace.py:587). Nothing lists
them, compares two of them or brings one back.

### Stops at every level

- Balanced stops at the research plan (C/review_policy.py:128-132), at "Review the first
  drafts" and at "Review the finished materials" (R/reviews.py:73-122).
- Automatic draft stops at each drawn deck (`deck_flow.PAUSES['automatic'] == ('final',)`,
  C/deck_flow.py:50-52) and at the finished materials.
- A change at the final review drops the first-drafts approval for anything but a scenario
  or a Yoodli layout (R/reviews.py:345-347). Piece 1 fixes the warning; the desk removes the
  cause for new trainings.

### A scenario does not know its plan changed

`scenario:*` has no inputs: `'upstream': ()` (S/workspace.py:392). A scenario is drafted from
the practice plan of its level's plan (`T/skills/training-studio/assets/examples/blueprint.md:32-33`,
`- main: roleplay. Objectives: O1, O2, O3. …`), so a change to that plan never reaches it.

### Citations are not checked

The guidance says "Cite findings with numbered references that resolve in Sources"
(`references/stages/document.md:30`, `brief.md:26`). No check reads `[n]`. The blueprint's
`[R:id]` and the brief's `<!-- findings: … -->` notes are checked by finding ID
(S/checks.py:13, 299). A free-text edit on a desk could drop a reference or add a claim with
none, and nothing would say so.

### "Desk" already names the page

S/desk.py serves the page; `training.py desk` starts it in a conversation; R/page.py:1 reads
"The runner's server: the desk's page, with the runner behind it."; `docs/desk.md` is titled
"The page". Blog Studio's writing screen is now "the desk", and every studio will use the
word for its editing screen.

### Corrections to the findings

- There is no `accept()` in S/workspace.py. Lines 834-846 are the accept-as-it-is branch of
  `_approve`; the person's way in is `decide(root, target, 'accept', note, by, seen)`
  (S/workspace.py:1013).
- `approve(root, name, accept_stale=None, by='chat')` takes no `seen`. `decide` does
  (S/workspace.py:1059-1061: "has changed since it was opened.").
- A deck outline's slides store the objectives they serve as `sources`. `serves` is only the
  name the page's shape gives it (R/deck.py:439-461 `shown`).
- There is no separate brand-audit step. The audit runs inside `deck-save` (R/engine.py:2695)
  and in each round (`_audit_round`, 2561).
- The guide's `<!-- covers: … -->` note sits under most sections, not every one: Summary,
  Check your understanding, Answer key and Glossary have none (assets/examples/document.md).
  "8. Sources" in a brief is a guidance convention; the checker only requires that the section
  exists (S/checks.py:301-308).
- R/pipeline.py:54 still says "nothing here can approve a draft". Under Balanced and Automatic
  draft the runner accepts drafts through `workspace.accept_policy` (S/workspace.py:883-901).
- Under Automatic draft today, intermediates are approved with `by: 'review-policy'` and
  count as approved for readiness. The person's approval is the final review's signature in
  `run['review_decisions']` (R/reviews.py:415-416), not a per-file approval.

## The design

### 1. Naming

People see **the desk** for the new screen, as in Blog Studio and Presentation Studio. The
page as a whole stays "Training Studio"; nothing person-facing says "desk" for the page.

In code, "desk" keeps meaning the page, so nothing existing is renamed:

- `S/desk.py`, `S/desk/` (the page's folder), `training.py desk` and `RunnerPage(desk.Page)`
  keep their names. Guidance and installed helpers call them.
- The new Training code is named for **drafts**: `R/drafts.py` (the desk's record, saves,
  holds and History), `R/draft_jobs.py` (section, selection and update jobs),
  `R/draft_finish.py` (Finishing), `S/desk/drafts.js` (the screen), routes under
  `/api/drafts/…`, tests `test_drafts*.py`.
- The shared parts are piece 3's `studio_core/drafting` and `ui-kit/drafting.js`.
- **How the page loads them.** The page loads `/drafting.js`, then `/app.js`, then
  `/drafts.js`.
  - `S/desk/drafting.js` is a link to `ui-kit/drafting.js`, as `style.css` and `markdown.js`
    are already links.
  - `S/desk.py` `PAGE` lists both files.
  - `marketing_studio/network.py` `STATIC` gains `/drafts.js`; piece 3 adds `/drafting.js`.
  - `core/studio_core/packaging.py` `shared_link` accepts the new link, as piece 3 makes it
    do for Blog Studio.
- The one shared word is the run's flow: `flow: "desk"` in `run.json` and in the session, as
  the audit settled for every studio.
- `docs/desk.md` becomes `docs/page.md` (Decision 12). Every link to it is updated. The new
  screen is described in `docs/the-desk.md`.

### 2. The start

A new training starts in a sheet of three numbered steps, as the layout rules ask for a
sheet that makes something. Its submit is **Start**, with Cancel beside it. There is no
review-level card and no "Where this training stops".

1. **Goal and audience.** The title, what the learner can do afterwards, who they are and
   what they already know, the time they have, and the purpose (Field enablement, Technical
   upskilling, General knowledge). These are today's first-step fields.
2. **Materials and levels.** The levels as chips (101 to 401; none for one training without
   levels). The materials as one set of chips: Learner guide, Reference brief (with its kind,
   product or competitive), Slide deck (PowerPoint or Google Slides; presented in a session or
   read on its own), Practice scenarios, and Yoodli. Yoodli needs the brief and practice, and
   its chip says so when they are off. Where pieces 1 and 4 reshape these controls, this
   sheet uses theirs.
3. **Sources and settings.** Documents, added here before Start and listed with Remove; your
   sites; the public web; research questions (at most 8 lines of at most 300 characters,
   checked as they are typed); brand (and look, Decision 1); copies (Google Docs, Word); and
   the assistant (agent, model, reasoning level). Then **Start**.

**Documents before Start.** The page holds the chosen files, as it does today
(`holdDocuments`, S/desk/app.js:5361). **Start** makes the training, then adds each held
document and says they are all added, in that order. The engine already waits for
documents before any research (`next.kind == 'documents'`), so nothing is researched from
part of them. A document that fails to add leaves the training waiting, and the progress
line says "One document could not be added: <name>. Add it again, or start without it."
with both actions.

**What Start sends.** Today's form, with `flow: 'desk'` and no review level. `Engine.start`
(R/engine.py:987) makes the run record with:

- `schema: 4` and `flow: 'desk'`;
- `research_contract`, required (Decision 3);
- no `review_policy` and no `review_layout`.

A run with no `review_policy` reads as Step by step (`review_policy.level`,
C/review_policy.py:71-79). That is deliberate: any engine path that misses the desk branch
stops for the person; it never runs on unseen. `read_record` accepts schema 4 only with
`flow == 'desk'` and a research contract of schema 2. `workspace.init` gains `flow='desk'`,
saved in the session. Start returns `gates: 0`.

### 3. Progress, with no stops

A desk training opens on its desk as soon as it is started. Until the start is done, the top
of the desk is one progress band:

- Its first line says whether the person is needed: "Nothing needed from you. Each material
  opens here as it is ready, in about N minutes."
- Below it: the current step in plain words ("Researching", "Planning level 101", "Writing
  the 101 guide", "Drawing the 101 deck"), from each step's `doing` words, and one clock for
  the whole start.
- N comes from piece 3's step-time estimate: this computer's median for each kind of step,
  else fixed minutes. The fixed minutes are research 6, a plan 1, a guide 3, a brief 2, a
  scenario 1 and a Yoodli layout 1 per level, and 1.25 a slide for a deck (`deck.RATE`).

Each card fills when its material lands. A card is read-only while something built from it
is being made in the start; it says "Being used to write the 101 guide. You can edit it when
that is done." Other cards can be edited, noted and marked ready during the start.

Every review stop goes for desk runs. What still needs the person moves to where it is
about:

| Today | On the desk |
| --- | --- |
| Failed after three tries | The progress band, or the card: **Try again** |
| Out of time | **Give it more time** |
| Out of money | **Carry on** |
| Agent could not be used | **Check this computer** (opens Status) |
| Account limit | "Wait, then Try again" |
| A worker's question | A question card at the top of the desk |
| A picture the deck needs | On the deck card, filled, with "Draw it without this picture" (piece 1) |
| A deck sent back to its words | A banner on the affected slide cards |
| A grave review finding or an audit blocker | "Needs you before using" on the card; it cannot be marked ready while one stands |
| No slides tool on this computer | The deck card says where it can be drawn |

**How the engine carries on.** In `Engine._work` (R/engine.py:1208-1233), a desk run takes
a new branch before the review-policy check. At a `gate`, `wait`, `outline` or `look` step,
the engine continues it on the desk:

- **gate:** `workspace.accept_desk(root, name)` (new, beside `accept_policy`). It approves
  with `by: 'desk'` and logs `continued-on-the-desk`.
- **outline:** the deck's words are kept with `by: 'desk'`, as `_policy_outline` does with
  `review-policy` (R/reviews.py:204-222).
- **look:** the brand's default look, as `_look_default` does (R/engine.py:1929), with the
  receipt's `by: 'desk'`.

This is `Engine._desk_gate`, beside `_policy_accept` (R/reviews.py:187-202). Each
continuation appends piece 5's receipt to `run['review_events']`: `{gate, by: 'desk',
evidence, at, decision: 'continued-on-the-desk'}`. It never counts as the person's approval
of a material (section 9).

Under desk runs `reviews.group` is not called, so no `review:*` step exists. Grave findings
do not hold the run (`pipeline.holding`), because the material would never reach the desk.
They are shown on the card and block Mark ready.

### 4. One desk per training

One screen per training:

- **Toolbar.** The training's title and Back. One filled action: **Mark this level ready**
  (or, once it is ready, **Publish** in a team workspace). Quiet actions: Download, Google
  Doc, Finishing.
- **Lede.** "Each level's materials, built from the shared research. Edit any part. Nothing
  is ready until you mark it."
- **What needs you.** One line, first, naming the cards that need the person: held,
  blocked or asking. Each name jumps to its card.
- **Level tabs.** 101 / 201 / … as a segmented control. A training without levels has no
  tabs.
- **The Sources panel**, shared by every level, as the desk's aside on a desktop and as its
  own tab on a phone. It holds:
  - the account of the research, from `research_view.account` (C/research_view.py): the
    brief, the check's word, findings, gaps and the sources read;
  - the research plan;
  - **Add a source** (section 8).

A level's tab is one column of cards, in this order:

| Card | What it holds |
| --- | --- |
| **Plan** | The level's blueprint: frame, objectives, modules, assessment and practice plans, open gaps. Typing, and a whole-plan note (section 5.4). Checked by `lint_blueprint`. |
| **Guide** | The learner guide as part cards (section 5). Checked by `document_coverage` and the new citation check. |
| **Brief** | The reference brief as part cards, its eight numbered sections fixed (section 5). Checked by `check_brief`. |
| **Deck** | Piece 5's slide cards (section 7). |
| **Practice** | One card per scenario (section 7.5). Checked by `check_scenario`. |
| **Yoodli** | One card per Yoodli layout, its fields laid out to copy (section 7.5). Checked by `check_yoodli`. |

A material the training does not make has no card. A material left out after Start shows
one quiet line: "Left out: …".

**Each card's head** shows:

- its state: Writing…, Draft, Ready, "Built from an earlier plan", or "Needs you before
  using";
- what was "Checked for you", from the in-process checks;
- **Mark ready**.

The checks are the ones in S/checks.py that take milliseconds, re-run after every change:

| Material | Check | Where |
| --- | --- | --- |
| Plan | `lint_blueprint` | S/checks.py:152 |
| Guide | `document_coverage` | S/checks.py:278 |
| Brief | `check_brief` | S/checks.py:326 |
| Practice | `check_scenario` | S/checks.py:395 |
| Yoodli | `check_yoodli` | S/checks.py:492 |
| Guide and brief | the new `citations` check | section 5.3 |

### 5. The guide and the brief as part cards

The desk shows a file as parts. The material's file stays the one copy of its text: every
save is written back to it, so downloads, copies, the index and the conversation helper keep
working.

**Piece 3's parts, given Training's store and codec** (`R/drafts.py`):

- **The store.** `TrainingStore(root)` implements piece 3's store
  (`drafting/store.py`):
  - `product`: "Training Studio". `word`: "training".
  - `held()`: whether the engine holds `engine.files`.
  - `folder(name)`: `work/drafts/<name>/` in the material's level folder. `work/` is
    never shared (R/gitstate.py:92 `IGNORED`), so this record is this computer's only.
  - `local(name)`: the waiting Finishing proposals, under `home.data_root()`.
  - `write(name, draft, parts)` does three things:
    1. calls `record.advance`;
    2. joins the parts and saves the file through `workspace.save(root, name,
       source=<joined>, edit=True, via=<kind>)`, then `workspace.accept_desk(root, name)`;
    3. records the file's hash in `draft.json` as `file_sha256`.
- **The record follows the file.** Before every read, `drafts.current(root, name)`
  compares the file's hash with `file_sha256`. When something else wrote the file (a step,
  a Google pull, the conversation helper, another computer), the file is split again:
  - each part keeps its id when its heading, or its covers or findings note, matches;
  - the revision goes up by one;
  - every part is marked changed, so a form opened before is refused with piece 3's "This
    draft changed since you opened it. Reload to see the latest."
- **The codec** (piece 3's `Codec`, with Training's hooks):
  - **The guide.**
    - The opening part is everything before the first `##`: the title, **For:**, **Time:**
      and the objectives.
    - Each `##` section is a part.
    - A section's `<!-- covers: … -->` line stays with it. It is shown as chips ("Covers
      O1, K1.1"), never as editable text.
    - **Sources** (the numbered list `[n]` resolves to) is a read-only part (section 5.3).
  - **The brief.**
    - The `# Product brief:` or `# Competitive brief:` title is the opening part.
    - Each `## <n>. <title>` is a part, in `BRIEF_SECTIONS` order (S/checks.py:301-308).
      Parts cannot be added, removed, renamed or reordered.
    - A section's `<!-- findings: … -->` note stays with it.
    - **8. Sources** is read-only.
  - `breaks(text)` refuses a `##` heading inside a part, as Blog's does.

#### 5.1 Notes and rewrites

- **Typing.** Piece 3's autosave: one second after the last keystroke, against the part
  revision the form saw.
  - Each save writes the file and the session at once.
  - It is committed with the training's next commit: at most one a minute while typing,
    and always before a job, a Mark ready, or when the person leaves the desk (the share
    call).
- **A section note.** "How should this change?" with **Rewrite**.
  - With no note, the button is **Write again**. It writes the section from its plan
    module, the sections before it and the findings it cites.
  - Both use piece 3's prompts: `edit_rule('training material')`, `SURGICAL_PART` and
    `request(label, text, scope, 'Training Studio')`.
  - Training adds the citation rule (section 5.3).
- **What a section job is handed.**
  - The section.
  - Its covers IDs.
  - The plan module those IDs belong to.
  - The neighbouring sections.
  - The findings the section cites, plus the findings behind its covers IDs. Each finding
    has a reference number given beforehand.
  - Earlier levels' "assume the reader can already" text (`_earlier`, R/pipeline.py:1601).

  The worker hands the section back with a new worker tool, `submit_part`:
  - it splices the part into the whole file;
  - it runs the material's full check (`check_document` or `check_brief`,
    R/worker_tools.py:501, 512) and the citation check;
  - it hands the problems back for the worker to fix, at most `SUBMISSIONS` times, as
    `submit_artifact` does;
  - a brief part must keep its numbered heading exactly.
- **The whole-guide note** (Decision 9). One box at the top of the Guide or Brief card.
  - Each section is revised in order with the whole file as context. This uses piece 3's
    `REVISE_ONE`, with "N of M sections" and Stop.
  - A section that fails leaves the others done.
  - **Write the whole guide again**, in the card's menu, is today's whole revise request
    (one `document` step).
- **Selection.** Selecting text in a part shows piece 3's selection bar: Rephrase, Shorten,
  Expand, Fix and Ask…. The passage, its section and the findings it cites go to a
  `selection` job (piece 3's `ACTIONS` and `passage_task`). The result replaces the
  selection, and the splice re-runs the checks.
- **Times.** Piece 3's `step_times.expected(store, path, key, guess)`, kept in
  `home.data_root()/draft-step-times.json`. The guesses, used until this computer has its
  own times, come from the measured anchors in the findings (section 5.3 there):

  | Action | Guess |
  | --- | --- |
  | A section note | 1 minute |
  | Write again | 2 minutes |
  | A selection | 1 minute |
  | The whole-guide note | 1 minute a section |

#### 5.2 When a job lands

A job carries its part and the part's fingerprint, its basis (piece 3's
`drafting/basis.py`).

- **The result lands only while the part is unchanged.** Training calls `land_part` or
  `land_selection` inside `settle`.
- **If the part changed** in the meantime, the result is set aside with piece 3's "The draft
  changed while this was being written. Run it again." Nothing is saved.
- **If it is unchanged,** the result is written through the store, holding `engine.files`.
  That is a save with `via` set to the job's kind, then an acceptance on the desk, then a
  commit.
- **`via`** is a new argument to `workspace.save`, recorded on the save event. It is one of
  `save`, `rewrite`, `revise-all`, `selection`, `restore`, `google` or `finishing`.
- **Piece 3's guard line** ("Check the facts: this changes a number.", `guards.flags`) is
  shown on the card under "Checked for you". It does not hold the rewrite.
- **An edit never clears what is out of date below it** (S/workspace.py:578, `edit=True`),
  and the material's own inputs are kept.

**One desk job at a time per training.** A second one is refused: "A change is already
being made to this training. Wait for it, or stop it." Desk jobs run in the training's own
queue, the engine's one-step-at-a-time loop (`_work`, R/engine.py:1208), so they take
`engine.files` and commit like any step (R/engine.py:108-111). During the start, a desk job
runs when the step under way ends, and its card says "Next, after drawing the 101 deck."
After the start, it runs at once. It never touches a card the start is still writing
(section 3).

#### 5.3 The citation rule

A new in-process check, `checks.citations(text, kind)`, for guides and briefs:

- every `[n]` resolves to an entry in Sources;
- every Sources entry is cited at least once;
- each paragraph a desk change added or rewrote that states a number, a name or a product
  claim and carries no `[n]` is listed as "A claim with no reference".

Problems show on the card under "Checked for you". The check never refuses a save. On a desk
run, its result joins the checks readiness reads (S/checks.py:668-672), so a reference that
does not resolve blocks readiness, as any failed check does. Saved runs and the
conversation's `training.py check` do not run it, so no saved training changes state.

What a desk job may do with references:

- It may cite only the numbered Sources the file already has, and the findings it was handed
  with their pre-assigned numbers.
- A handed finding it cites is appended to Sources by the runner, in the guide's
  `n. <title>, <date>, <URL or document>` form, or the brief's ``n. Finding `id`: …`` form.
- A reference the job drops is not refused, because a note may remove a claim. The card says
  "This change dropped reference [2]." with Restore beside it.
- A job never writes Sources itself. `submit_part` refuses a part that changes a Sources line.

The research rules stand: quotes are verified word for word, unresolved findings never back
a claim, and gaps are listed in the Sources panel.

#### 5.4 The plan

The Plan card holds the blueprint's sections as parts in the same way. Typing saves with
`via: 'save'`. A note on the plan is one whole-plan job: today's blueprint revise request
with the note. Section jobs are not offered on the plan: its modules, objectives and
practice plan depend on each other, and `lint_blueprint` checks them together.

A change to the plan reaches the guide, brief, deck and Yoodli layouts of its level (section
10). The card lists what it reaches, and their price, before anything is rewritten.

### 6. Selection edits and History

**History** is on every part of the guide, brief and plan, on each scenario and each Yoodli
layout, and on each slide (section 7). It uses piece 3's History sheet: versions newest
first, each with **Compare** (the word diff) and **Restore**. A restore is itself a
version.

**Where a text material's versions come from** (Decision 8). Every save of a material
already keeps the whole file by content (`snapshot`, S/workspace.py:493-501). Each save is
an event with its time and hash (S/workspace.py:587). `drafts.HistoryVersions` implements
piece 3's `Versions` interface (`keep`, `versions`, `counts`) over those files, with no file
of its own:

- `keep` records nothing. `workspace.save` has already kept the file. The kind of change
  and the page's session token go on the save event as `via` and `session`.
- `versions(name, part)` builds the list:
  1. The material's `save` events, newest first, each with its hash, time and `via`. Old
     events have no `via`.
  2. Each version is read from `.training-studio/history/<name>/<sha256><suffix>`. A version
     whose file is missing is skipped.
  3. History files that no event names are added last, as "An earlier version" with no
     time. These are copies kept before a hand edit outside the desk.
  4. Each version is split by the codec, and the part is matched across versions by
     heading, then by its covers or findings note, then by position.
  5. Consecutive versions whose part text is the same fold into one. Saves from one editing
     session fold into the earliest.
  6. At most 20 are kept per part, piece 3's cap.
- **Labels.** A version is labelled by the change that came after it, as in Blog Studio:
  Saved, Rewritten, Revised with the whole note, Selection, Restored, "Before Google's
  text", Finishing. An event from before the desk has no `via` and reads "Saved".

Nothing is migrated. A training saved before the desk has History the day it opens on the
desk, as far back as its history files go. Where piece 3's `Desk` builds its own `Versions`,
Training's `TrainingDesk` subclass passes `HistoryVersions` instead.

**Restore** saves the version's part text into the current file with `via: 'restore'`,
through the same path as a save. A restore of a whole scenario or Yoodli layout restores the
file.

### 7. The deck

The deck card is piece 5's slide cards, with piece 5's meaning for each control:

- the drawn picture;
- the slide's words, typed in place, with the selection bar;
- the speaker notes as their own edit;
- the slide's review and brand findings;
- "How should this slide change?" with **Redraw slide N**, which changes how the slide is
  drawn;
- History.

The card also has piece 5's whole-deck note with Stop and "N of M sections", its price
lines, and its Outline view. Training uses these as piece 5 defines them. What Training
needs beyond piece 5 is listed below. Training's deck runner is its own (R/engine.py
`_split`, `_sections`, `_whole`, `_review`, `_keep`; R/deck.py), so each piece 5 action is
wired to it.

1. **Keeping unchanged sections.** Training's deck start (`_split`, R/engine.py:2271-2366)
   starts every section afresh. It gains Presentation Studio's rule: a section whose slides
   say the same, in every field its composer reads, in a deck that is otherwise the same, is
   kept as drawn.
   - The rule is `_kept` with `DRAWN_FROM` (Presentation's build.py:1071-1107).
   - The kept section's file is copied under the new start's name and marked `kept`.
   - For Training, the fields compared are every field its outline stores but `id`:
     `kind, title, subtitle, understand, points, caveat, source, notes, sources`
     (R/deck.py:361 `rules`).
   - If piece 5 or piece 2 moves this rule into core, Training uses that. Otherwise
     `R/deck.py: kept_sections` follows the same rule with Training's field list.
2. **The slide note redraws its section only.**
   - The note is kept in `run['deck'][<level>]['notes']`, piece 5's shape `{id, slide,
     section, note, at, by, status}`.
   - Training's `section_work` (R/pipeline.py:1999) gains the person's notes as its focus,
     in the way it already takes "what the review found" for a repair.
   - The other slides of the section are frozen. `submit_section` refuses a change to one
     with piece 5's sentence: "this slide has no requested repair. Keep its drawing
     unchanged."
   - The chain is: that section, then the whole deck merged and rendered (`_whole`), then the
     review of changed slides only, whose findings wait on their slides as proposals with no
     repair round (Decision 13), then the deck saved with its audit (`_keep`).
   - The deck lands as a Draft. It takes about 3 to 6 minutes and $0.40 to $1.50, against
     about 10 minutes and $3.20 for eight slides today.
3. **Words and speaker notes.** Piece 5's chains, wired to Training's files:
   - **Typed words and selection edits** follow the same chain:
     1. the slide's field changes in `deck/outline.json`, checked by `deck.rules`
        (R/deck.py:361);
     2. the same text is patched into the drawn section;
     3. `deck.kept` and the compile check whether it fits;
     4. the deck is merged and rendered.

     If the words do not fit, nothing is saved. The card offers **Redraw with these words**
     (priced) or **Discard**, as piece 5 decides.
   - **Speaker notes** change the outline's `notes` and the drawn section's notes together.
     The deck is then merged and rendered with no worker, so `deck.kept` still passes.
4. **Update from the guide** (section 10.3) is Training's own.
   - A scoped `deck-outline` job words again only the slides found. The run record's
     `deck[<level>].asked` gains `slides: [ids]`.
   - The job is told to copy every other slide exactly. `check_outline`
     (R/worker_tools.py:601) refuses an outline whose other slides changed.
   - Then the deck is split again, keeping unchanged sections, and only the changed
     sections are drawn.
5. **Slide History** is piece 5's per-slide version store, with Training's folders:
   - the words go in `<level>/deck/versions/<slide-id>.jsonl`, which is shared;
   - the drawings go in `<level>/work/deck/versions/`, which is not.
6. **Per level.** One deck per level. Each is its own card on its level's tab, with its own
   History, notes and holds.
7. **Try another look** (Decision 1).
   - It runs the existing `deck-look` step (one slide in each look) and opens the shared
     `lookPicker`.
   - **Apply** redraws the whole deck. It is priced first with `deck.before(slides)`, or with
     the last draw's cost (`stops.redone`) where there is one.
8. **Pictures.** The picture supply is on the deck card (R/page.py:705 `asset`), with piece
   1's "Draw it without this picture".
9. **On another computer** the drawn pictures are not there. A teammate's slide cards show
   words only, as `docs/runner.md:347` says today. Nothing is drawn again unasked; **Draw it
   here** is priced, as in piece 5.
10. **There is no Deliver.** A training's deck is kept by `deck-save`, and **Mark ready** is
    the person's approval of it.
11. **The rules stay.**
    - The brand.
    - Harness Slides' confinement.
    - "A finding about what a slide says is never fixed for you."
    - The grave-finding rule: a deck with a grave finding open cannot be marked ready.

#### 7.5 Scenarios and Yoodli

- **A scenario card** is the whole file, editable, with a note: `scenario_work` with the note
  (R/pipeline.py:1676). That takes 20 to 60 seconds. A scenario the person wrote is never
  rewritten: its card offers typing and History, and a note only lays it out in their words,
  as today (R/pipeline.py:32-34).
- **A Yoodli card** shows the fields laid out to copy, with their limits from
  `assets/profiles/yoodli.json`. It takes a note: the `yoodli` job, then `check_yoodli`.
  Nothing is posted to Yoodli. It needs the brief and practice, as today.
- **The missing input, fixed for desk runs only** (section 10.3). A scenario's inputs gain
  `practice`: the hash of its own line in its level's practice plan (`- <id>: …` under
  `## Practice plan`). A scenario saved before the desk keeps no inputs, so it never reads as
  out of date on opening.

### 8. Add a source

**Add a source** in the Sources panel opens a sheet:

1. **Add.** Documents, as at the start (Decision 11).
2. **What it changes.** The price of a research update. It is the core's
   `research_view.price` with what the person sees again: "Updating the research reads it
   again with these documents: up to 3 rounds. Last time it took 31 minutes and about
   $9.80." Then: "Afterwards each level's plan and brief, and any deck without a guide, say
   what changed. Nothing else is rewritten until you update it."

Then **Update the research** with Cancel beside it.

**What it does** (`drafts.add_source`):

1. While holding `engine.files`:
   - each document is added through the documents store (R/documents.py:480 `add`). The
     `SETTLED` refusal stays for the start's own documents step and does not apply here;
   - a training researched from the public web only gets a documents list (scope `mixed`),
     and its pinned `research_from` gains documents, with `widened_at`;
   - a research request is recorded through `workspace.decide(root, 'research', 'revise',
     note, by='page')`, with the note "Sources were added: <titles>. Read them, and update
     what they change. Keep everything else.";
   - `run['research']['again']` is recorded, as a research request is today
     (R/engine.py:3620-3625);
   - the findings' fingerprints before the update are kept in
     `run['drafts']['findings_before']`.
2. The research step runs again under the contract, with the documents in its sources (up
   to three author and check rounds). That is 5 to 10 minutes, and more if rounds repeat.
3. The new research is accepted on the desk. The Sources panel marks findings **New** or
   **Changed** against `findings_before`.
4. Everything built from the research is now out of date and held (section 10): each
   level's plan, each brief, and each deck where the guide is left out.

### 9. What must stay

- **Levels.**
  - Per-level folders.
  - Every plan is written before the first guide.
  - "Assume the reader can already" from earlier levels (`_earlier`).
  - One tab per level.
  - Adding a level after Start is out of this piece.
- **Mark ready is the person's approval.**
  - Mark ready is `workspace.decide(root, name, 'approve', by='page', seen=<the hash the
    card showed>)`. It is refused when the material changed since the card was drawn.
  - It is refused while the material is held or a grave finding stands.
  - An edit afterwards drops the material back to Draft, as the core already does
    (S/workspace.py:640-641).
  - **Mark this level ready** marks each card of the level in order: plan, guide, brief,
    deck, practice, Yoodli. It stops at the first that cannot be marked, and says why.
- **Who approved what.** The desk's acceptance (`by: 'desk'`) keeps the chain whole, so
  that `_approve`'s rule (every input approved, S/workspace.py:826-830) still holds. It is
  never shown as Ready.
  - `workspace.person_statuses(root, session)` is new. On a desk run it reads a plan or
    material approved `by: 'desk'` as `draft`. The intake, the research plan and the
    research keep `approved` (Decision 7).
  - Readiness, the package step and copies read `person_statuses` on desk runs.
- **Readiness and the package.** `checks.readiness` (S/checks.py:644) is unchanged. On a
  desk run it is given `person_statuses`, so every plan and material must be Ready. The
  `package` step writes the index once every wanted material of every level is Ready, with no
  stop. A "kept as it is" decision is listed as a limitation beside today's `accepted-stale`
  ones.
- **Copies and the Google Docs round trip.**
  - Copies are made on Mark ready (Decision 5). **Send to a Google Doc** on a card makes or
    updates its Doc at once.
  - **Bring the Doc's changes in** is offered whenever Google has changed (piece 1 fixes when
    it appears).
  - A pull lands as a version: `gdocs.pull` already saves with `edit=True`
    (S/gdocs.py:330-334), and now also passes `via='google'`. History says "Before Google's
    text".
  - The both-changed choice (R/copies.py:217-233) and the hidden covers and findings notes
    (S/gdocs.py:34) are unchanged.
  - A heading that lost its note in Google is named on the card (piece 1 returns `unplaced`).
- **Downloads.** Download (the server's file name and extension, as piece 1 fixes), the Word
  copies, and the index.
- **Yoodli.** It requires the brief and practice. The profile stays in its one file. Fields
  are laid out to copy, and nothing is posted.
- **Team rules.**
  - One computer drives a training. Every desk route goes through the engine's `_held(path)`
    and `team.ours`.
  - A teammate reads the desk with no notes, edits or Mark ready, and is offered **Take
    over**.
  - Hand over, clash recovery and **Share now** are unchanged.
  - Under "share after each change", desk work is shared:
    - on each Mark ready, Update, Keep as it is and landed job;
    - and when the person leaves the desk, as Blog Studio shares on leaving.

    It is not shared on each typed save.
- **Research rules.** Quotes are verified word for word, unresolved findings never back a
  claim, and gaps are listed. Research stays in Harness Research; slides stay in Harness
  Slides.

### 10. How a change reaches what was built from it

Inputs stay whole-file hashes (S/workspace.py:358-398, 468-482):

| Material | Built from |
| --- | --- |
| plan | intake, research |
| guide | plan |
| brief | plan, research |
| deck | plan, and the guide (or the research when there is no guide) |
| scenario | nothing today; its practice plan line on desk runs (section 7.5) |
| Yoodli | plan, brief, scenario, and the Yoodli profile |

**10.1 Held, not remade.**

- On a desk run, a material whose inputs changed after it landed is **held**:
  - `pipeline.survey` drops the steps of every held material before choosing the next step.
    The material is not made again and its gate does not come up.
  - `drafts.held(root, session, run)` names them: every material whose status is out of date
    and whose file exists, less those with an update asked for in
    `run['drafts']['updates']`.
  - Saved runs keep today's remaking unchanged.
- The card says, for example, "Built from an earlier guide: 3 sections changed since." The
  words name the input and count the parts that changed, from History. It offers two
  actions:
  - **Update from the guide.** A sheet previews what changes and its price, then
    **Update**.
    - The price comes from `reviews.rewritten` (R/reviews.py:124) and `stops.redone`
      (C/stops.py:70), with `deck.before` for slides.
    - Update records `run['drafts']['updates'][name] = {at, by: 'page', scope}`. The
      material's own step runs again; the update closes when it lands.
  - **Keep as it is.** `workspace.keep_as_is(root, name, reason=None, by='page', seen)`
    (new):
    - it records `{decision: 'kept-as-is', from, to, reason, by, at}`;
    - it sets the material's inputs to the current ones;
    - a Ready material stays Ready (its approval's inputs move with it). A Draft is accepted
      on the desk again.

    It is refused while an input is itself held: "Update or keep the plan first."
- A card whose input is held says "Waiting for the plan to be updated or kept." and offers
  neither action.

**10.2 Text updates are surgical.** **Update from the plan** on a guide or brief:

- The job is handed the old material and the change between the plan it was built from (its
  history file) and the plan now.
- It is told to change only what that change requires and keep every other section word for
  word, so the person's edits survive.
- Its result goes through `submit_part`'s checks for each part it changed. The old text is
  kept as a version.
- The preview names the sections the change touches.

**10.3 Deck updates are scoped by what slides serve.**

- **Update from the guide** on a deck:
  1. The guide's sections that changed are found by comparing the guide the deck was built
     from (its hash in the deck's inputs, read from history) with the guide now, part by
     part.
  2. Their covers IDs are mapped to objectives. A key point `K1.2` belongs to objective
     `O1`, by the plan's numbering.
  3. The slides to update are those whose `sources` name one of those objectives.
  4. Only those slides are worded again (section 7.2) and only their sections drawn again.
- When no slide serves a changed section (a glossary edit), the sheet says "No slide is
  built from the sections that changed." and offers **Keep as it is**.
- **Update from the plan** on a deck scopes by the objectives whose lines changed. When
  objectives were added or removed, the whole outline is worded again, and the price says
  so.

**10.4 Scenarios.** On desk runs, a change to a scenario's practice plan line holds it: "The
plan for this practice changed." **Update from the plan** drafts it again (`scenario_work`
with the changed line). A scenario the person wrote offers only **Keep as it is** and typing.

**10.5 Plan edits fan out.** A saved plan change holds its level's guide, brief, deck and
Yoodli layouts. The Plan card lists them with one price for all and **Update everything
below**. It runs them in order (guide, brief, deck, Yoodli) as one chain with Stop. Nothing
runs until it is pressed.

**10.6 Research updates fan out to every level.** Each level's tab shows its held cards. The
Sources panel offers **Update every level** with the summed price, run level by level with
Stop.

### 11. Stops, review levels, approvals and the state-transition matrix

- **Review levels.** New trainings have one flow, the desk.
  - The form stops asking "Where this training stops". Training's own Settings line for
    the level goes.
  - Step by step, Balanced, Automatic draft and the combined reviews (layouts 1 and 2) stay
    for saved runs. A run with `review_policy` or `review_layout` keeps its gates and
    screens.
  - The shared `review.level` in the studios-config file keeps governing saved runs and
    Presentation Studio's saved decks. Its controls go in piece 7.
- **Review stops** (research plan, research, plan, guide, brief, deck words, look, deck,
  scenario, Yoodli, first drafts, finished materials). None on desk runs. Each is continued
  on the desk with a receipt (section 3).
- **Problem stops stay** and move to the progress band or their card (section 3).
- **Approvals** become **Mark ready** per material and **Mark this level ready**: each one is
  its own `decide` with `seen`.
- **The state-transition matrix**
  (`T/docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`, section A7) gains
  these rows. Each takes the next free number on the base it lands on (131 at cc53056, after
  piece 1's rows), and each has its `test_row_NNN_*` test:

| Row | Given | When | Then |
| --- | --- | --- | --- |
| D1 | A new training from the desk start | Start, with documents added before it | Run schema 4, `flow: 'desk'` in the run and the session, no `review_policy` or `review_layout`; intake approved by the page; documents added and marked done before any research step |
| D2 | A desk run at any gate, outline or look | The engine reaches it | Continued with `by: 'desk'`, an event `continued-on-the-desk` and a receipt in `review_events`; no stop; `person_statuses` reads a plan or material so accepted as `draft` |
| D3 | A desk run with no Harness Research synthesis | Start | Refused with "Update Harness Research to start a training on the desk."; nothing made |
| D4 | A part on the desk | Saved with the hash it was shown | `save(edit=True, via='save')`; inputs kept; accepted on the desk again; a Ready material is Draft; what was built from it is held |
| D5 | A section or selection job | Lands with its part unchanged / changed | Unchanged: spliced, checked, saved with `via`, the old text a version. Changed: set aside with the "changed while this was being written" sentence, nothing saved |
| D6 | A part's version | Restore | Saved with `via='restore'`; the text it replaced is itself a version |
| D7 | A desk run; a material whose inputs changed | Survey | Held: not made again, no gate; card says what it was built from |
| D8 | A held material | Update from its input | `updates[name]` recorded; only that material's steps run (deck: scoped slides); lands as Draft; update closed |
| D9 | A held material | Keep as it is, with or without a reason | Inputs set to the current ones; `kept-as-is` decision; Ready stays Ready; readiness lists it as a limitation; refused while an input is held |
| D10 | A Draft material, nothing held, no grave finding | Mark ready with the shown hash / a changed hash | Approved `by: 'page'`; refused with "has changed since it was opened." when the hash differs |
| D11 | A level with several cards | Mark this level ready | Each marked in order; stops at the first that cannot be, naming why |
| D12 | Every wanted material of every level Ready | Survey | `package` writes the index with no stop |
| D13 | A desk run after research | Add a source | Document added; research request recorded; research runs again; each plan, brief and guide-less deck held; findings marked new or changed |
| D14 | A drawn deck | A note on one slide | Only that slide's section drawn again, its other slides frozen; review of changed slides only, its findings proposals on their slides with no repair round; deck Draft |
| D15 | A drawn deck | Speaker notes changed on one slide | Outline and drawn notes rewritten, deck compiled, no worker; deck Draft |
| D16 | A drawn deck | Another look applied | Whole deck drawn again in that look; deck Draft |
| D17 | A drawn deck | Typed words on a slide that fit / do not fit | Fit: outline and drawn section patched, deck merged, no worker, deck Draft. Do not fit: nothing saved; Redraw with these words or Discard |
| D18 | A deck built from an earlier guide | Update from the guide | Only the slides whose `sources` meet the changed sections' covers are worded again, other slides unchanged; unchanged sections kept; deck Draft |
| D19 | A material with a Google Doc changed in Google | Bring the Doc's changes in | Saved with `via='google'`; History shows "Before Google's text"; both-changed choice as today |
| D20 | A finished saved training | Open on the desk | `flow: 'desk'` and `opened_on_desk` added; materials approved by the page, or under a final review the person approved, show Ready; its review screens refused afterwards |
| D21 | A desk run; a scenario's practice plan line changed | Survey | That scenario held with "The plan for this practice changed"; a saved run's scenario is never held |
| D22 | A desk run / a saved run | A review or gate route / a desk route | Refused, each with a sentence naming where it is decided |
| D23 | A Finishing proposal | Apply | Swapped in as a version (`via='finishing'`); skipped items unchanged |
| D24 | A desk run's step | Fails three times / runs out of time or money | No gate: the problem shows on the progress band or its card with its action |

  Piece 1 owns the missing rows it names: Google pull and choose, picture supply, Redesign,
  and looks that could not be rendered.

### 12. Finishing

An optional side panel (piece 3's Finishing shell and proposals). Each tool proposes. The
person sees before and after, then chooses **Apply**, **Edit** or **Skip**. Each Apply keeps
a version.

**In process, no job:**

| Tool | What it finds |
| --- | --- |
| Proofread | Piece 3's mechanical checks |
| Coverage gaps | An objective or key point no guide section covers (`document_coverage`) |
| Claims with no reference | From the citation check |
| Scenario format | `check_scenario` |
| Yoodli limits | `check_yoodli` |

**Jobs, each priced before it runs:**

- **Check against sources.** Per claim: supported, not in the sources, or contradicted. It
  reads the research record; it never researches. Apply rewrites the sentence to what the
  finding says, or removes it.
- **Fit the learner's time.** The guide (and deck words) sized to the intake's Time, with
  per-section cuts or additions.
- **Check the answer key.** Each answer says why it is right and why a plausible
  alternative is wrong.
- **Humanize** (light, medium, strong), from Blog Studio, with Training's citation rule.
- **Level check.** Anything an earlier level taught that this level teaches again
  (`_earlier`).

### 13. How saved trainings keep working

- A run without `flow: 'desk'` keeps its gates, its review screens and its remaking, exactly
  as today. The engine branches only on `flow`.
- A finished saved training (state done, nothing waiting) offers **Open on the desk**
  (Decision 10).
  - Its files are already the desk's format: guide sections are `##`, brief sections are
    numbered, and its history is under `.training-studio/history`.
  - Opening adds `flow: 'desk'` and `opened_on_desk: {at, was: {review_policy,
    review_layout}}` to its run record. The run schema stays as it was. `read_record`
    accepts `flow` on any schema.
  - The session gains `flow: 'desk'` too.
  - Materials approved by the page show Ready.
  - Materials approved `by: 'review-policy'` under a final review the person approved (its
    signature in `review_decisions['final']`) show Ready as well, from
    `opened_on_desk.was`.
  - Its scenarios keep no inputs (section 7.5).
- A training waiting at a gate stays on its review screens until it is finished.
- A conversation-made training (approval mode `chat`) reaches the desk only after it is
  brought in ("Run this from here") and finished. `training.py desk` and the conversation
  page are unchanged.
- The legacy research question queue, pre-0.16 deck branches and words-only deck gates stay
  untouched (piece 7).
- Desk routes refuse saved runs, and review routes refuse desk runs, as piece 5 does
  (`drafts.on_desk(run)`, like piece 5's `decks.on_desk`):
  - on a desk run, `decide`, `/api/review`, `/api/outline` and the gate routes refuse with
    `drafts.ON_DESK`: "This training is on the desk. Change it there.";
  - on a saved run, the desk routes refuse with `drafts.NOT_ON_DESK`: "This training is not
    on the desk. Use its own screen, or open it on the desk once it is finished."
- **Guidance.** Desk runs never use the conversation guidance's gates.
  - `workspace.init(flow=…)`, `accept_desk`, `keep_as_is`, `save(via=…)` and
    `person_statuses` are helper changes.
  - The conversation guidance does not call them, so `minimum_runtime` does not move.
  - If guidance is changed to mention the desk, `minimum_runtime` in `guidance/manifest.json`
    and `VERSION` rise together.

### 14. Delivery

Each pull request is usable on its own, after pieces 1 to 5.

1. **New trainings run on the desk.**
   - The desk start (documents before Start), the schema 4 run and continuing on the desk.
   - The progress band, and problem stops on cards.
   - The desk with level tabs, the Sources panel and read-only cards.
   - Mark ready and Mark this level ready, `person_statuses`, readiness and package.
   - Holds with **Keep as it is**, and **Update** as a whole-material remake.
   - The scenario's practice input, copies on Mark ready, and downloads.
   - Usable: a new training runs to the end with no stops, and the person marks it ready.
2. **Editing text on the desk.**
   - Part cards for the plan, guide and brief; typing; section notes; Write again; the
     whole-guide note; selection edits.
   - The citation check, `submit_part` and History (old trainings included).
   - Google pulls as versions, surgical **Update from the plan**, and **Open on the desk**
     for finished saved trainings.
3. **The deck on the desk.**
   - Piece 5's slide cards, and kept sections in Training's deck start.
   - Slide notes with frozen slides, typed words and selection edits, speaker notes as
     their own edit, and slide History.
   - **Update from the guide** scoped by covers and serves, and **Try another look**.
4. **Add a source.** The sheet, the priced research update, new and changed findings, and
   **Update every level**.
5. **Finishing.** The in-process tools, then the job tools.
6. **Docs.** `docs/the-desk.md`, `docs/page.md`, the README and `docs/runner.md`.

## Out of scope

| What | Piece |
| --- | --- |
| The Google pull trigger, `unplaced` headings, download names, picture "Draw it without this picture", the matrix rows for pull, picture supply, Redesign and unrendered looks, one vocabulary for the materials | 1 |
| The shared runner modules Training forks from Presentation Studio, the out-of-date docs | 2 |
| `studio_core/drafting` and `ui-kit/drafting.js`: version shape, split and join, the basis rule, prompts, proposals, the estimate, History, the selection bar, the progress line, the Finishing shell, part cards | 3 |
| The layout of Training Studio's other screens and the shared components out of `blog.css` | 4 |
| Slide cards, slide History, notes-only writes, the look picker on the desk | 5 |
| Chat starting desk work; removing the gated flows, the review-level controls and the legacy research queue | 7 |
| Adding a level after Start; links as sources; real-time token streaming | Later |

## Testing

Disposable settings, workspaces, Git identities and data folders, through
`T/tests/helpers.py` and `runner_support.py`. Scripted workers from `tests/stand_ins` and a
synthetic research bundle (`synthesis_fixture.py`). No provider job, no Google call, no
Harness Slides beyond the deck contract stand-in, and nothing in the owner's studio.

- **Matrix rows D1 to D24**, each a `test_row_NNN_*` test in `test_workspace.py`,
  `test_runner_engine.py` or `test_drafts.py`.
- **Splitting and joining.** Every example in `assets/examples/` (guide, both briefs,
  blueprint) splits and joins back byte for byte. Covers and findings notes stay with their
  section, and brief parts cannot be added, moved or renamed.
- **History from history files.** A training made with the core helper and saved three
  times, plus one hand edit, lists four versions of a section, the hand edit last with no
  time. Restore is a version.
- **The citation check.** A reference that does not resolve, an unused Sources entry, a
  dropped reference, and a new claim with no reference.
- **Jobs.** One job per training. A job that lands on a changed part is set aside.
  `submit_part` refuses a changed Sources line and a renamed brief heading.
- **Holds.** Guide edit holds the deck, and Update from the guide names only the slides
  whose `sources` meet the changed sections' covers. A glossary edit names none. A plan line
  change holds only its scenario.
- **Deck.** A one-slide note keeps every other section's drawn file (the deck contract
  stand-in counts sections drawn). A notes-only change runs no worker.
- **Saved runs.** A Balanced run, an Automatic draft run and a Step by step run walk their
  gates unchanged. Open on the desk shows Ready per section 13.
- **Page journeys** in `test_desk.py` through `page_harness.js`:
  - the start's three steps with documents;
  - progress to the desk;
  - a section note;
  - History and Restore;
  - a selection edit;
  - Mark this level ready;
  - a held deck with Update and Keep;
  - Add a source;
  - Finishing Apply;
  - a teammate's read-only desk;
  - the phone layout.
- **The full Training Studio suite** before each merge
  (`python3 studios/training/scripts/ci/run_tests.py`), the root suite, and the shared Tart
  runner on macOS before the last.
