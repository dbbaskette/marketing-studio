# Piece 2: cleanup and the shared runner: design

**Date:** 2026-10-26, at main cc53056 plus the audit documents. **Owner's words:** "Lets
apply our UI changes to blog studio to the other studios. We also need to do an audit of
workflow and clean it up", and, asked whether that meant the layout rules or the writing
desk as well: "1 and 2".

This is piece 2 of the order of work in
[the audit summary](2026-10-26-workflow-audit.md): "What is safe to delete now, the stale
docs, and the shared runner: the modules the deck studios copy move into
`core/studio_core` with the product name passed in, as `server.py` and `studios_config.py`
already are." Piece 1 (workflow fixes) merges first. Every file and line below is at
cc53056; re-read each on piece 1's merge before changing it.

The findings this spec draws on are beside the summary:
[Presentation Studio](2026-10-26-workflow-audit/presentation.md) sections 3a to 3f,
[Training Studio](2026-10-26-workflow-audit/training.md) sections 3a to 3f and the section 3
addendum, and [Blog Studio and shared setup](2026-10-26-workflow-audit/blog-and-shared.md)
Part A.3 and Part B.4. Each item quoted here was checked against the code; where the code
disagreed with a finding, this spec says so.

## What is wrong now

### Code that no screen and no command reaches

**Blog Studio** (paths under `studios/blog/skills/blog-studio/`).

- The old Polish and Google Doc intake screens still exist. `sPolishIntake`
  (`assets/management/runner.js:359-400`, "Polish a document", "Open for polishing") and
  `sGooglePage` (`:142-180`, "Open your manuscript") are reached only by a typed
  `?screen=polish|draft|google`; the router keeps `'google','draft','polish'`
  (`runner.js:105`, `:114-116`) and the poll skip list keeps them (`:315`). Their helpers
  `sGoogleResult` (`:133-141`) and `sGoogleButton` (`:125-127`) have no caller.
  `sGooglePreview` (`:129`) is still used by the desk start (`desk.js:197`).
- The library's Upload one file dialog still offers "Start an editable blog from this file"
  (`assets/management/index.html:43`, `app.js:646` `as_blog`, and the Bring in sheet's
  "…or start an editable blog from it", `runner.js:1100`). It makes a manuscript-editor blog
  (`scripts/management.py:943-960`), not a desk blog, against
  `docs/design/blog-workflows.md`: "Every new blog starts on the writing desk". The polish
  intake is the only other caller of `as_blog: true` (`runner.js:388`).
- The page's `run-create` route (`management.py:2154`, `:2272`; `blog_runner.dispatch`
  `create`, `blog_runner.py:3163-3177`, with its `.blog-runs/creations` ledger) has no page
  caller. Chat starts runs through the CLI's `create`, not this route. Its form-only fields
  `review_level`, `review_seen` and `review_default` (`blog_runner.py:1237-1253`,
  `:1527-1529`) came from the removed "Where this run stops" chip.
- The private writing default `stop` (`DEFAULTS['stop'] = 'package'`, `blog_runner.py:103`)
  was read only by the removed wizard.
- The `source-keep` route (`management.py:2001`) lost its caller, the files screen's Keep
  tick. The function `management.source_keep` stays: `desk.py` uses it.
- Page code nothing calls: `sBrandNotice` (`runner.js:325`, and its Home brand poll),
  `renderRun` (`runner.js:311`, called only by `check-management.cjs:1332,1335`),
  `views.runs` "Writing runs" (`app.js:48`) with its `view==='runs'` branch (`app.js:230`),
  and the third field of each `BLOG_MODES` entry (`runner.js:5`; only the label is read, at
  `:183`).
- `blog.css` rules no markup uses: `.studio-hidden-controls`, `.blog-search`, `.stage-link`,
  `.file-actions`, `.review-compare`, `.empty-invite`, `.blog-facts`,
  `.manuscript-original`, `.editor-suggestions`, `.finish-summary`. The finding also listed
  `.view-library`; that one is used: `app.js:242` sets `table.className='table view-'+view`.
- Comments that name removed screens: `management.py:826` ("this computer's start form")
  and `:924` ("as on the files screen"); `blog_runner.py:396`, `:1245-1246`, `:2843`;
  `tests/test_blog_runner.py:2198`.
- `assets/management/training-studio-ui.json` pins `style.css` and `markdown.js` by hash to
  the retired `training-studio` repository, but both files are now links to `ui-kit/`.

**Presentation Studio** (paths under `studios/presentation/`; `D` is
`skills/presentation-studio/scripts/desk`).

- `D/app.js:3139` `asksFor()` has no caller and lists every stop as if Step by step.
- `D/app.js:3685-3686` draws `'bead-later'` when `found.at === 'later'`; `stagesOf` never
  yields `'later'`. `D/deck.css:25-32` styles it, under the comment "Rehearsing with Yoodli
  is shown dimmed, as coming later."
- `firstDraftChoice()` (`D/app.js:2873`) and `siteShown()` (`:2977`) are one-line wrappers;
  the section comment at `:6912-6914` is there twice.
- `runner/worker_tools.py:497` `as_kept()` has no caller in Presentation Studio (Training
  Studio's copy is used). `runner/brand.py:423` `look_status()` and
  `runner/steps/build.py:529` `guided()` are called only by tests.
- The `rehearse` step: "Rehearse (coming later)" (`runner/stages.py:72`) sits in every deck,
  never runs, and is special-cased in `stages.py:94,170,213-219`, `engine.py:175,186,3141`,
  `jobs.py:128`, `D/app.js:3643,3723` and core `review_policy.py:124-125`.
- `D/app.js:3964` calls `window.TrainingStudioMarkdown`, the name `ui-kit/markdown.js:358`
  gives the shared renderer. Blog Studio's and Training Studio's pages use the same name.

**Core and ui-kit.** `deck_flow.CHECKPOINTS` (`core/studio_core/deck_flow.py:47`) and
`research_view.REFRESH` (`research_view.py:107`) have no reader. `.looks .look-choice`
(`ui-kit/style.css:1764`) matches nothing: `deck-panels.js` draws `.deck-look`.
`deck_flow.DESIGN_SESSION` and `SHARED_INPUTS` are read only by the deck contract tests;
they stay, because those tests are the contract.

### Saved-work paths that new work can still land in

These four paths serve saved work, so they cannot be deleted on a code read. Two of them
are not only for saved work.

1. **The legacy research question queue.** When `research_contract.snapshot()` returns
   None (a Harness Research without `scripts/lib/synthesis-cli.mjs`, or any read error,
   `core/studio_core/research_contract.py:129-150`), a new deck
   (`presentation/runner/engine.py:772-778`) or a new training
   (`training/runner/engine.py:1023-1029`) starts on the old 30-question queue with no word
   to the person. The conversation path already refuses: "Install the shared Harness
   Research 1.0 or newer before importing synthesis research."
   (`training/skills/training-studio/scripts/workspace.py:752`). Training Studio's docs say
   the queue "can go once no workspace holds such a run" (`docs/runner.md:379`,
   `docs/how-it-works.md:24`), which is false while new runs can still reach it. Both
   suites' research stand-in (`tests/stand_ins/research.py`) is the legacy queue CLI, so the
   journey suites drive the queue for every new run.
2. **The cover sample for a brand skill without looks**
   (`presentation/runner/steps/look.py:59-122,329`; `engine.py:1492-1503`). A skill older
   than 0.14.0 stops the deck (`engine.py:1391-1395`), but a versionless skill, or a saved
   deck whose `brand/brand-contract.json` came from an older skill, still reaches it. Its
   state lives in `work/look/`, which only the building computer has.
3. **Review layout 1** (`training/runner/reviews.py:17-22`: no `review_layout` reads as 1).
   A saved training needs it while its run has no `review_layout`, a level other than Step
   by step, and has not passed `review:final`.
4. **Pre-0.16 Harness Slides branches** (`runner/slides.py` in both studios: "a tool that
   lists none", 0.13.1 and 0.14.1 paths) behind a floor of 0.16.0 (`slides.py:186`). No saved
   work needs them; a deck carries on in its gate shape, not its tool version.

Nothing today tells anyone which saved runs still need which path.

### The deck studios carry one runner twice

Presentation Studio's `runner/` was ported from Training Studio's and both are kept by
hand. `vendor.json` records 81 ported files; `studios/presentation/AGENTS.md:11` keeps the
fork as the rule: "Every file taken from Training Studio is listed in `vendor.json` with the
file it came from and the revision." The copies have drifted both ways: Presentation alone
has `agents.data_shared()`, `brand.told()` and `gitstate.made_apart()`; Training alone has
the locked `share_when` decision and the address check in `gitstate.own_share`.

Measured at cc53056 with `diff` and a definition-by-definition comparison (each top-level
function, constant and method compared as text; "words" means the same once product and
item words are set aside):

| Module | Lines P / T | Diff lines P / T | Definitions: same, words only, different, one side only |
| --- | --- | --- | --- |
| `brand_source.py` | 364 / 364 | 1 / 1 | 30, 1, 0, 0 |
| `companion.py` | 250 / 249 | 4 / 3 | 13, 0, 1, 0 |
| `research.py` | 148 / 143 | 14 / 9 | 16, 0, 2, 0 |
| `agents.py` | 755 / 741 | 27 / 13 | 61, 0, 3, 2 |
| `brand.py` | 443 / 426 | 31 / 14 | 38, 0, 2, 4 |
| `team.py` | 377 / 377 | 35 / 35 | 21, 11, 3, 0 |
| `gitstate.py` | 796 / 791 | 62 / 57 | 44, 10, 4, 3 |
| `documents.py` | 647 / 575 | 101 / 29 | 53, 4, 5, 5 |
| `settings.py` | 504 / 464 | 129 / 89 | 30, 2, 11, 12 |
| `setup.py` | 733 / 719 | 230 / 216 | 24, 4, 13, 9 |
| `slides.py` | 876 / 893 | 143 / 160 | 65, 0, 11, 14 |
| `upkeep.py` | 1429 / 1354 | 248 / 173 | 50, 28, 19, 11 |
| `worker_tools.py` | 2052 / 2319 | 409 / 676 | 120, 1, 26, 38 |
| `page.py` | 556 / 815 | 413 / 672 | 8, 0, 21, 44 |

The first eight are one module each with a few product words and a few one-sided
changes. The last six share a common part (179 to 877 lines) inside studio-specific
code. Two values that look like product words are saved formats:

- the published tag: `presentations/<deck>/r3` (`presentation/runner/team.py:36,308`)
  against `training-studio/<folder>/<id>/<number>` (`training/runner/team.py:36,308`);
- the workspace files `gitstate` writes: `README.md`, the ignore lines and `hub.json`, each
  naming its studio and folder (`gitstate.py:89-111` in each).

### Training Studio keeps its own copies of core helpers

- `skills/training-studio/scripts/desk.py:700-737` class `Desk` is core `server.Desk`
  (`core/studio_core/server.py:431-470`) word for word but one docstring word, and
  `desk.py:617` `text()` is `server.py:107`. desk.py already builds `_security` from
  `server.for_product` (`desk.py:58-65`). Its `SECURITY_HEADERS` dict (`:41-47`) is
  overwritten at `:65`; `HOST` (`:30`) and `JSON` (`:40`) feed only the copied `Desk`.
- `scripts/cmd_desk.py:8-48` (`NOT_A_PERSON`, `interrupt`, `port`, `has_a_screen`, `show`,
  `announce`) repeats `server.py:53,119-155`.
- `runner/setup.py:246` `same_address` is `core/studio_core/workspace_setup.py:22`.
  Presentation's `runner/setup.py:297` is a third copy.
- `runner/claude-code-models.json` is a second regular file, byte for byte the same today,
  beside Presentation's `runner/claude-code-models.json`, which
  `core/studio_core/claude-code-models.json` links to. `docs/runner.md:350` tells people to
  edit "that file alone", and `tests/test_runner_agents.py:838,846` pins that path.

### Docs that say the wrong thing

- **Presentation Studio.** `README.md:29` "The page stops at each of these and waits for
  you" holds only at Step by step. `docs/runner.md:61` describes the cover-only brand step.
  `README.md:34` and `runner.md:190` contradict each other on an old brand skill, and the
  code refuses it. `runner.md:125` says the page "does not offer this yet"; it does
  ("Bring in a deck"). `README.md:151-164` sit after "## Licence" and repeat earlier lines;
  `runner.md:135,184,221-227` repeat `:53` and `:63`. `README.md:129` and `runner.md:63` say
  "Deliver to Google Slides"; the button says "Send to Google Slides". `capabilities.md:17`
  calls the look picker "cover preview"; `:37-38` says rehearsal "is labeled as future
  work". `references/workspace.md:17,31,34`, `references/levels.md:9-10` and
  `references/routes.md:7,23` speak of the cover and the brand stop. `docs/development.md:3`
  and `vendor.json:3` point at the retired `dbbaskette/training-studio`; `:89` pins
  harness-slides v0.14.2 (the pin is 0.16.0). The finding also said `:84` ("A release is a
  `vX.Y.Z` tag on `main`") is wrong; it holds: releases are now the suite's `v4.x` tags, and
  `upkeep.TAG` reads `v?X.Y.Z`. `README.md:145` calls the 2026-10-14 design
  "the full specification".
- **Training Studio.** `docs/runner.md:347` "Bringing edits back from a Google Doc … are not
  in the runner yet" contradicts `:192`. `runner.md:379` and `how-it-works.md:24` (the
  queue "can go once no workspace holds such a run"). `references/levels.md:22` "more than
  30 questions" against `stages/research-plan.md:35,56` (1 to 8). `README.md:210` sends
  issues to `dbbaskette/training-studio`. `README.md:3` is a 200-word paragraph on review
  levels in a README that is "for a new user". `docs/desk.md:68,85` describe the
  conversation page only ("It does not start or run a training"). `runner.md:201-217` puts
  the slide-design session first though it is off by default. `docs/acceptance.md:9-30`
  records 2026-10-12 runs on harness-research 0.8.0 with no date of record.
  `docs/development.md:3` and `how-it-works.md:3` call the 2026-10-12 design "the full
  specification". `runner/engine.py:76-82` notes describe sub-floor tools.
- **Blog Studio and shared setup.** `docs/design/blog-workflows.md` "Interface contract"
  (from line 21) states old-run gate and editor rules as current.
  `studios/blog/docs/epic-27-validation.md`, `startup-validation.md` and
  `google-gcloud-validation.md` are linked from nowhere. `docs/shared-setup.md:137-140`
  says "A Blog Studio run includes research with the outline…" without saying that is a
  run started in chat.

## Design

The work is three parts: delete what is dead, make the saved-work paths retirable, and
share the runner. Deletions go first so that less code moves.

### 1. Blog Studio deletions

1. **The old intake screens.** Remove `sPolishIntake`, `sGooglePage`, `sGoogleResult` and
   `sGoogleButton`. Keep `sGooglePreview`. The router sends `?screen=google|draft|polish`
   to `desk-start`, as it already sends `?screen=new` (`runner.js:104`), and the three names
   leave the router list and the poll skip list. The journeys that test only these screens
   (`check-management.cjs` `taskJourneys` from `:459`, `googleReopening` `:486-528`,
   `googleIntake` `:529-586`, the `sRoute('polish')` navigation at `:289-290`) go. Before they
   go, the "already linked Doc reopens" case moves to a desk-start journey on
   `sDeskReadGoogle` (`desk.js:189-197`).
2. **The upload's server branch.** Piece 1 turns the Upload one file tick into "Then edit
   it on the desk" (the page opens the desk start with the file as the draft) and stops
   sending `as_blog`. This piece removes what is left: the server's `as_blog` field and
   branch (`management.py:872`, `906-912`, `943-960`), and `as_blog:false` from the
   voice-sample upload (`runner.js:636`) if piece 1 left it. A request that still sends
   `as_blog` gets the existing "Unknown upload field." (`management.py:866-878`). The tick
   itself stays as piece 1 left it.
3. **The `run-create` route and its form fields.** Remove the route, `dispatch('create')`,
   the `.blog-runs/creations` ledger and the fields `review_level`, `review_seen` and
   `review_default`. Chat's CLI `create` is unchanged. Tests that used the route move to the
   CLI `create` where they test the pipeline (`test_authenticated_http_pipeline_completes_all_gates`)
   and are deleted where they test only the chip.
4. **The `stop` default** leaves `DEFAULTS`, the save check (`blog_runner.py:499-500`) and
   the test fixtures (`check-management.cjs:442,530`). The reader already keeps only keys in
   `DEFAULTS` (`blog_runner.py:413-417`), so a saved `stop` is ignored and dropped at the
   next save. A page opened before the change that sends `stop` gets the existing "Save the
   displayed writing settings only." and saves after a reload.
5. **The `source-keep` route** goes; `source_keep` stays. Its route tests call the function.
6. **Unused page code and rules** listed above go, with `renderRun`'s two journey calls
   switched to `sRun`. `BLOG_MODES` keeps only id and label.
7. **The UI provenance pin** `training-studio-ui.json` goes, and
   `references/package-notes.md:26` says the page's stylesheet and Markdown renderer are
   Marketing Studio's `ui-kit`. `training-studio-LICENSE.txt` stays: the code came from
   there.

### 2. Presentation Studio deletions

1. The dead page code and CSS above go. `firstDraftChoice` and `siteShown` are inlined.
2. `as_kept`, `look_status` and `guided` go, with the tests that are their only callers.
3. **The rehearsal placeholder.** The `rehearse` step leaves `stages.PIPELINE` and every
   special case. A saved `run.json` that holds `gates.rehearse` or `steps.rehearse` still
   reads: every reader looks steps up by name in `stages.steps(run)`, so an unknown key is
   never visited. A test loads such a record and checks the survey, the timeline and the
   status sentence. `review_policy.automatic`'s presentation tuple loses `'rehearse'`.
   README's "Rehearsal is not part of a deck yet" stays true.
4. **The shared renderer's name.** `ui-kit/markdown.js` sets `window.StudioMarkdown`. Every
   page and journey that reads `window.TrainingStudioMarkdown` reads the new name. The old
   name is not kept: all readers are in this repository.

### 3. Core and ui-kit deletions

`deck_flow.CHECKPOINTS`, `research_view.REFRESH` and `.looks .look-choice` go.
`DESIGN_SESSION` and `SHARED_INPUTS` stay.

### 4. Making the saved-work paths retirable

Piece 7 removes these paths. This piece adds what lets piece 7 know when.

**4.1 Start refuses without synthesis.** Presentation Studio's start, when research is
asked for, and Training Studio's start, always, take the research contract before they
write anything. When `research_contract.snapshot()` gives None, Start refuses with:

> Research needs Harness Research 1.0 or newer on this computer, and the one here cannot
> do it. Update Harness Research, then start again.

Nothing is created: no folder, no record, no remembered item, no commit. A deck without
research starts as today. Trainings and decks brought in from a conversation are not
starts and are not refused. Each runner's `engine.py` gets `LEGACY_RESEARCH = False`: "True
lets a new run start on the legacy question queue. Only the test suites that still drive the
queue through its stand-in set it; piece 7 removes it with the queue." Each suite's
`StudioCase` sets it True, because the research stand-in is the legacy queue CLI. The new
refusal tests set it False. Piece 7 replaces the stand-in with a synthesis one.

**4.2 A saved-work scan.** Each deck studio's runner gets `studio saved-work`, read-only:
it starts nothing, changes nothing and asks nothing online. It prints JSON:

```json
{"paths": [
  {"id": "research-queue", "about": "...", "needed_by": [{"path": "...", "title": "...", "why": "..."}]},
  ...],
 "unused": ["review-layout-1"]}
```

`unused` lists every path no saved item needs. The checks, each from the studio's own
readers:

| Path | Studio | A saved item needs it when |
| --- | --- | --- |
| `research-queue` | both | its run has no `research_contract`, its plan includes research, and research is not done (Presentation `stages.survey(run).done`; Training `engine._survey(root, record).done`) |
| `research-queue` | Training | a conversation training (`home.trainings()`) whose `session.json` has no `research_contract` and whose `research` status is `not-started` |
| `cover-sample` | Presentation | it is not delivered and either has `look.md` without `work/look/shown.json`, or has `brand/brand-contract.json` and has not reached `gate:look` ("may need it": the contract can come from an older brand skill) |
| `review-layout-1` | Training | its run has no `review_layout`, `review_policy.level(record) != 'step_by_step'`, and `review:final` is not done |
| `old-harness-slides` | both | never: the entry says "No saved work needs these. They are reached only by a Harness Slides that lists no capabilities." |

It looks at every item the runner drives in this computer's workspace (Presentation
`engine.every()`, Training `engine.trainings()`) and at any `--folder PATH` given. It never
reads another computer's `work/`, so the cover-sample answer is for this computer; the
output says so in its `about`. The words and JSON shape live in a new core module,
`core/studio_core/saved_work.py`, so both studios say the same.

### 5. The shared runner

**5.1 Where it lives.** A new package, `core/studio_core/shared_runner/`. It is a package of
its own because core already has `companions.py` (installer pins) and each studio already
has a package named `runner`.

**5.2 The host contract.** `shared_runner/__init__.py` says what a studio must give: a
`runner` package that puts its scripts folder on the import path (as both do today), and
the scripts modules `workspace` (with `WorkspaceError`), `home`, `hub`, `sync_guidance` and
`studios_config`. A shared module imports its fellow modules only through `runner`
(`from runner import companion, settings`), never as `studio_core.shared_runner.x`, so each
process has one object per module. No shared file names a product, an item word or a data
variable; those are values passed in.

**5.3 Whole modules move behind a facade.** `brand_source`, `companion`, `research`,
`agents`, `brand`, `team`, `gitstate` and `documents` each become one file in
`shared_runner/` with a `for_product(name, product, **values)` that calls
`studio_core.modules.fresh_module`, as `studios_config.for_product` does. Each studio's
`runner/<name>.py` becomes a facade in the shape `runner/studios_config.py` already has:

```python
"""Training Studio's team: the shared runner's, for this studio."""
import sys

import runner  # noqa: F401  puts the core on the import path
from studio_core.shared_runner.team import for_product

sys.modules[__name__] = for_product(__name__, 'Training Studio', ITEM='training',
                                    NOTIFY='TRAINING_STUDIO_NOTIFY', TAG_UNDER_TOOL=True,
                                    REVISION_MARK='')
```

The module object a test patches (`mock.patch.object(team, ...)`) is the shared module
itself, so every patch point stays. `fresh_module` registers the new module under its name
before it runs it, so a dataclass in it finds its own module.

**5.4 Common parts are bound into the studio's module.** `settings`, `setup`, `slides`,
`upkeep`, `worker_tools` and `page` keep their studio file. The definitions both copies
share move to `shared_runner/<name>.py` and are bound into the studio module with a new
`studio_core.modules.bind(namespace, source, names, methods=None)`, the generalization of
`companions.bind`: each function is rebuilt with the studio module's globals, each listed
method is set on the studio's class the same way (plain functions, properties, static and
class methods), and each listed constant is copied. A bound function reads the studio's
names, so the studio's constants and every test's patches apply as today. `bind` refuses a
function that uses zero-argument `super()` (its `__class__` cell would name the shared
class) and a name the studio module defines itself. `worker_tools` stays a script the
agent runs by its path (`worker_tools.command`), so only a bound design works there.

**5.5 Rules for reconciling the copies.**

- Where the studios differ on purpose, the difference is a value passed in: the product,
  the item word (`deck`, `training`), the data variable, the published tag shape, the
  workspace folder and its files, what marks an item's folder, and paths a studio owns
  (`brand.PINS`, `upkeep.INSTALLER`).
- Where one copy has a later change the other lacks, the shared module keeps it for both,
  with a test in the studio that gains it. The changes each studio gains:

| Module | Presentation Studio gains | Training Studio gains |
| --- | --- | --- |
| `companion` | — | `run_command(..., env=None)` |
| `research` | — | omitting a null headline (its findings carry none today) |
| `agents` | the tool labels for `submit_judgements` and `submit_coverage` | `data_shared()` with `TRAINING_STUDIO_DATA` (not yet called) |
| `brand` | `contracts()` | `told()`: the brand skill is told the runner's `HARNESS_SLIDES_ROOT` and `HARNESS_RESEARCH_ROOT` |
| `gitstate` | `own_share` needs an address; `share_when` decides under the studios-config lock | `made_apart()` |
| `documents` | — | `add_text`, `text_of` and document titles (not yet called) |

- Where the two differ in a sentence only, the shared module keeps Presentation Studio's
  wording with the product and item words passed in, unless Training Studio's test quotes
  its own. `agents._safe` keeps Presentation's refusal.
- For the six partial modules, only definitions the same in both copies (as text, or but for
  product and item words) move. A definition that differs in substance stays in each studio.

**5.6 Order.** One module per task, the least drift first: Training's own copies of core
helpers; the model list and `same_address`; the package and `bind`; then `brand_source`,
`companion`, `research`, `agents`, `brand`, `team`, `gitstate`, `documents`; then the common
parts of `page`, `settings`, `setup`, `slides`, `upkeep` and `worker_tools`. Each studio's
whole suite runs after each task.

**5.7 Saved formats stay as they are.** No file a studio writes changes by a byte: run
records, session files, published tags, the workspace `README.md`, ignore lines and
`hub.json`, the documents index, `runner.json`, the upkeep record. Before each module moves,
a test in each studio pins what it writes today; it passes before the move and after.

**5.8 Training Studio's copies of core helpers.** `desk.py` takes `Desk` and `text` from
`_security`, with `Desk` a subclass whose default page is Training's `Page`; the dead
`SECURITY_HEADERS` dict, `HOST` and `JSON` go. `cmd_desk.py` keeps its `serve` and takes
`NOT_A_PERSON`, `interrupt`, `port`, `has_a_screen`, `show` and `announce` from core
`server`. Both runners' `setup.py` take `same_address` from `studio_core.workspace_setup`.

**5.9 One Claude model list.** `core/studio_core/claude-code-models.json` becomes the one
regular file; both runners' copies go. Both runners' `settings.CLAUDE_MODELS` point at it.
Packaging's special case for that link goes. `model_catalog.claude_models` keeps reading
the same file; folding the two readers into one is not needed for one list.

**5.10 Records of provenance.** `studios/presentation/vendor.json` keeps an entry for each
file it lists; each moved file's note becomes "Original port provenance retained. The
implementation now comes from `core/studio_core/shared_runner/<name>.py`." (whole modules)
or "…The parts both deck studios share come from `core/studio_core/shared_runner/<name>.py`;
the rest is this studio's." (partial modules), as `server.py` already reads. The two
model-list entries go with the file. A top-level `note` says the source repository is
retired and Training Studio lives in `studios/training`. Presentation's `AGENTS.md` rule
becomes:

> **Shared runner parts live in core.** A runner module both deck studios use lives in
> `core/studio_core/shared_runner/`, and `runner/<name>.py` passes the product in. Change
> it there, for both. A file still copied from Training Studio is listed in `vendor.json`
> with the file it came from and the revision.

Training Studio's `AGENTS.md` gets the same rule's first two sentences. `docs/core-status.md`
gains a row for the shared runner. Blog Studio's `studio_sync` and `studio_brand` copies
and their vendor records are not part of this piece.

### 6. Docs

Each stale line above is corrected to what the page and code do on piece 1's merge. Lines
whose truth depends on a piece 1 fix (Presentation `README.md:3` and `runner.md:222`,
`README.md:32`, the PowerPoint-on-another-computer line, Blog `page-tools.md:49`) are piece
1's. Specs called "the full specification" are named as history, with `docs/runner.md`
named as current. The retired repository's links go, except where they record where code
came from. `docs/design/blog-workflows.md`'s old-run rules move under a heading "Blogs
started before the desk". The three unlinked Blog validation records get a first line:
"A record of a check made on <date>; it describes the studio as it was then."

## Out of scope

- Broken paths and wrong page copy, in every studio and Marketing Studio's setup: piece 1.
- Moving Blog Studio's desk parts to `studio_core/drafting` and `ui-kit/drafting.js`:
  piece 3.
- The layout rules, and moving the shared components out of `blog.css`: piece 4.
- The deck desk and the training desk: pieces 5 and 6.
- Removing the legacy research queue, the cover sample, review layout 1, the pre-0.16
  branches and their stand-ins; a synthesis research stand-in; chat starting desk blogs;
  the gated pipelines and review level controls: piece 7.
- Sharing the engine machinery (`jobs`, turns, claims) and `studio.py`: no piece yet.
- Blog Studio's `studio_sync` and `studio_brand` copies of `gitstate`, `team` and `brand`: no
  piece yet; they carry Blog adapters.
- The settings migrations "From an earlier version" (`settings.own`, `gitstate.own_share`):
  they go after a release or two, not here.

## Testing

- Every deletion is checked by grep for its names across page scripts, `index.html`, the
  server, guidance and tests before it goes, including class names built from a prefix
  (`'view-'+view`).
- Blog Studio: `python studios/blog/scripts/ci/run_tests.py` and
  `node studios/blog/scripts/ci/check-management.cjs`, with the moved "already linked Doc
  reopens" journey and the `?screen=polish` address landing on the desk start.
- Presentation Studio: an old `run.json` with `gates.rehearse` reads; the start refusal;
  the scan on a disposable workspace holding one deck for each check and one that needs
  nothing.
- Training Studio: the start refusal leaves no folder, record or remembered training; the
  scan on a disposable workspace; `desk.Desk()` still serves Training's page.
- Shared runner: root tests for `bind`, `fresh_module` registration and the host contract
  (no product names, no direct imports of fellow shared modules); in each studio, a test that
  every moved module comes from core and every bound name resolves in the studio module,
  and per module a test that pins what it writes before the move.
- Root suite `PYTHONPATH=.:tests python -m unittest`, and each studio's whole suite after
  each shared-runner task. Tests use disposable settings, workspaces, Git identities and
  data folders, stand-ins and scripted workers. No provider, Google or assistant job runs.
