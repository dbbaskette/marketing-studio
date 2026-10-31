# Shared studio setup

Marketing Studio, Blog Studio, Presentation Studio and Training Studio read the
same settings file and use the same setup page. Completion means choices were
saved and the requested workspace preparation succeeded, not that provider sign-in
or every optional tool is available.

| Starting state | Action | Result | Verification |
| --- | --- | --- | --- |
| No settings or partial settings | Open any independent studio | Complete shared setup form; no provider job starts | `shared_setup_acceptance.journey` |
| Standalone setup open | Finish | Current studio opens its normal home; shared completion recorded | `shared_setup_acceptance.journey` |
| Setup complete in another studio | Open an unconfigured studio later | Shared workspace adopted, normal home opens | `shared_setup_acceptance.journey` |
| Completed global setup, older private defaults | Launch/migrate | Shared choices, including automatic defaults, win; private copies removed | `SharedSetupTests.test_native_runners_consume_live_shared_model_brand_and_preview_choices`, `ConfigTests.test_completed_shared_setup_keeps_empty_defaults_over_legacy_private_choices` |
| Existing workspace, new global root | Open again | Existing workspace retained | `SharedSetupTests.test_launch_adopts_local_defaults_once_and_preserves_existing_workspaces` |
| Invalid config or failed preparation | Finish | Error; no completion marker written | `SharedSetupTests.test_failed_workspace_setup_does_not_mark_global_setup_complete` |
| Another studio changes a setup choice during preparation | Finish | Ask to review settings again | `SharedSetupTests.test_concurrent_change_during_finish_requires_another_review` |
| Marketing Studio setup complete | Independently open any studio | Normal native home, shared model and preview defaults | `native_launch_acceptance.py`, `SharedSetupTests.test_native_runners_consume_live_shared_model_brand_and_preview_choices` |

Shared choices: person, assistant/model/reasoning, local work root or team
repository/branch/sharing, brand repository/release/identity/variant/installed skill,
delivery format, slide preview method, and research sites. Work already created retains its own
choices. Native workspace migration never moves existing content.

When no assistant is saved, setup uses the one Marketing Studio was installed for
(`target` in its `installation.json`). Without a single target it uses an installed
assistant, preferring Codex as the installer does, and otherwise Claude Code. The
setup snapshot offers this choice as `assistant_default`; finishing setup saves it.
`marketing-studio doctor` reports a problem when neither assistant is installed or
when the saved or default assistant is missing.

Default brand chooses a brand offered by the installed brand skill; default variant
chooses one of that brand's variants. For example, `tanzu` and `light` offer Tanzu
light branding when starting new work in each studio. These are starting choices,
not a requirement for every project. Existing blogs, presentations and trainings
keep their saved brand. The brand skill repository supplies templates and guidelines;
saving its address does not install or update the skill. Installation remains an
explicit action in a studio's settings. **Where is your brand skill?** offers
**Git repository** and **Installed skill folder** as separate, optional inputs.
A repository address does not require an installed folder. Leave the folder
blank for automatic discovery, or use it to select an existing installation.
The optional release tag is under **Advanced → Brand skill release**.

Optional studio controls retain built-in defaults: writing tone, time/spending
limits, parallel work, notifications and update checks. Research scope, author
voice, deck audience, training levels and similar content choices are selected
when starting work. Provider sign-in and installation remain explicit actions;
computer checks explain what is missing.

Run `scripts/ci/shared_setup_acceptance.py` for fresh independent-launch journeys
with disposable homes, synthetic Git identities and background provider/update
actions disabled. It is included in the full suite's acceptance gate.

## What a studio card says before it opens

Each launch card says, in words on the card, what Marketing Studio can honestly tell
before the studio opens, with the one action that fixes what is missing:

| Card | Meaning | Recovery |
| --- | --- | --- |
| **Can open** | Shared setup is finished, and the chosen assistant and Git are on this computer | None needed; sign-in is checked when a task needs it |
| **Needs setup** | Shared setup is unfinished, or the assistant or Git was not found | **Finish shared setup**, or **Check this computer** |
| **Not checked** | The shared settings file could not be read, or Marketing Studio did not answer | **Review shared settings**, or open the new private link |
| **Not installed** | The studio is not installed | **Install**, which you do yourself |

The **Ready when you are** card below the studios separates the three kinds of check:
what Can open covers; **This computer** (Git identity, Node.js and optional tools), which
is **Not checked** until you ask, then **Checked** or **Needs setup** with the items to
fix; and **Accounts**, assistant sign-in and Google access, which each studio checks when a
task needs them. Looking at Studios, its refresh and **Check this computer** run no
assistant, sign in to nothing, install no studio, prepare no workspace and start no paid
work: they look for commands on this computer and read Git's own settings.

## Models by task

In **Shared settings → Advanced → Models and reasoning**, choose
**One model** or **By task**. Each profile can inherit the shared model above,
use the assistant's default without model or reasoning flags, or select a model
and reasoning level from dropdowns. **Enter a model ID…** supports custom or
unlisted IDs. Saved IDs remain selectable when a catalog changes or cannot load.
Codex choices come from its read-only CLI model list. Claude Code uses the studios’
existing bundled model reference, with its source and date shown; that list does
not establish availability in your account. **Refresh models** retries a failed
listing without changing saved settings or starting a provider job. A failed listing
says why when the reason is known, such as Codex not being found or not finishing;
the CLI's own output is not shown.
Changing assistants requires reviewing the profiles before saving them.

| Profile | Tasks |
| --- | --- |
| Quick | Presentation Studio classification and extraction; Blog Studio source classification |
| Main | Research planning and questions, synthesis, teaching blueprints, writing, slide construction and ordinary independent review |
| Complex | Dedicated slide repairs in Presentation Studio and Training Studio; returning a Blog Studio review to its draft for repair |

Training Studio currently has no separate model-based extraction step. Its research
and writing use Main, and dedicated slide repairs use Complex. Compilation,
rendering, exporting and other deterministic steps do not start model jobs.
Retries keep the same profile. Review stays on Main even after a Complex repair.
Routing uses structured pipeline steps, never words in your prompt or another
model call. A model that fails is not replaced with another model.

New blogs, presentations and trainings save resolved profiles and the routing
policy in their run record. Later shared edits affect new work. An explicit
work-level assistant/model/reasoning choice that differs from the shared choice
uses that single model for the work. Older records retain their single-model
behavior. Job records distinguish requested choices from actual model/effort;
actual values remain unknown when the CLI does not report them.

Profiles live in the existing `studios-config.json`, under `models`, with schema 1,
mode `single` or `by_task`, assistant binding `agent`, and `profiles.quick`,
`profiles.main`, `profiles.complex`. Each contains `selection` (`inherit`,
`provider_default`, or `explicit`), and optional `model` and `effort`. Every studio
reads this same file; nested saves use its adjacent lock, preserve unrelated
settings, and reject conflicting stale edits.

## Research sites

Research in every studio may look in your documents, your sites and/or the public
web. Your sites are a list of base URLs kept under `research.sites` in the studios
config, edited on Shared settings' **Advanced → Research sites** part (not in first-run setup):

```json
"research": {"sites": ["https://blogs.vmware.com/tanzu", "https://docs.example.com"]}
```

Each site is https only, a public host and an optional path, with no query, fragment,
credentials or custom port; private, loopback and local names are refused. The list
is deduplicated, holds at most 50 and is shown as `host/path`. Saves go through the
adjacent lock, keep unrelated settings, and refuse a form that read an older list.
Each studio's start form starts from this list, may untick sites or add one for that
piece of work only, and the run pins the list it used. With your sites on and the
public web off, every page a research job saves must be under a listed site (exact
host, path at a segment boundary, every redirect checked); see
[the design](superpowers/specs/2026-10-23-research-sites-design.md) and
`core/studio_core/research_sites.py`.

## The Document Library

One local library holds documents for every studio. The code is in
`core/studio_core/document_library/`, and the design is in
[the spec](superpowers/specs/2026-10-29-document-library-design.md) and
[the plan](superpowers/plans/2026-10-29-document-library-plan.md).

**Where it is.** `library.root` in the studios config names its folder. Until the
first explicit use, the folder is `library/` under `local.root` (normally
`~/Studios/library`), and nothing is written. Explicit uses are an upload on
Marketing Studio's **Library** screen, a finished or published blog, or a delivered
deck. On the first one, the resolved folder is saved through the config's adjacent
lock, with unrelated values and formatting kept. If another studio saved a
location first, that one is used. A later change to `local.root` never moves the
library. Browsing, or opening any studio, makes nothing and sets up no workspace.
`STUDIOS_LIBRARY` names a library for one process, as `STUDIOS_CONFIG` names the
config file. Tests use it, and it is never saved.

**What it keeps.** Each document has a stable ID and immutable revisions under
`documents/<id>/revisions/<n>/`:

- `revision.json` holds the type, origin, studio, project and revision,
  representations with their SHA-256 hashes, and conversion state and gaps.
- `content.md` holds the readable Markdown.
- An upload also keeps `original.<ending>`, its bytes as they were sent.

Each revision is written whole into a hidden folder and then renamed into place.
Every write holds `.library.lock` (an interprocess `flock`). The catalog in
`.state/catalog.json` is rebuilt from the records whenever it is stale or damaged.
Each studio's browsing filters are kept in `.state/filters.json`; they are filters
only, never a selection.

Every file is checked against its hash before it is previewed, downloaded or
pinned, and a link, a missing file or a changed file is refused. Some files can't
be added as context until their text is supplied: an image-only PDF is marked
**Needs text**, and an unreadable file is marked **Cannot be read**. Nothing is
read with OCR, a model or the network.

| Content | Kept |
| --- | --- |
| Upload | Original bytes, plus Markdown when its text can be read |
| Finished or published blog | Its Markdown, under `blog:<blog id>` |
| Delivered deck | Slide-ordered outline Markdown, under `presentation:<deck folder>`. The PDF is recorded as **needs export**. |

**Choosing context.** **Add from library** pins chosen revisions into one project,
after checking every one of them first:

- **Presentation Studio** copies each revision into the deck's `sources/supplied/`
  as an ordinary supplied document, with `library` naming the ID, revision and
  Markdown hash. The deck's research, outline and words jobs read it within the
  existing 40-document and 8 MB limits.
- **Blog Studio** makes each revision a file uploaded for that blog (material) with
  the chosen role. An example stays an example. These files never enter the team
  library or the Team Hub.

A project keeps its copy if the library changes or is gone. A newer revision is
shown as available and is taken only on request. Removing a source removes the
project's copy, never the library document. Choosing context starts no research,
grants no web access and sends nothing to an assistant.

**State changes**

| Action or condition | Result |
| --- | --- |
| Add | Every revision is checked. All are pinned, or none |
| Add a document already pinned | Refused; Update instead |
| Remove | The project's copy is removed; the library document is unchanged |
| A newer library revision | The project shows Update available; nothing changes until the person takes it |
| Library changed, unavailable or deleted | The project keeps reading its pinned copy |
| Unreadable, changed or missing revision | Refused with why, and nothing changes |
| Finish, publish or deliver again with the same text | Same document and revision, and no new revision |
| A library save fails after delivery | Recorded in the deck's local `sources/library.json`. **Keep in library again** retries from `deliver.json`, with no upload and no job. |
| A job is already running | It keeps the copy of its sources that it took when it started. Adding context follows the desk's existing source rules. |

## Where new work stops

Choose **Where new work stops** under You and your assistant. New browser
runs in Presentation Studio and Training Studio, and Blog Studio runs started step by step
in chat, save this choice. A new blog on Blog Studio's writing desk has no stops: its
outline and draft are written after Start, and you edit them when you choose.

| Choice | Reviews |
| --- | --- |
| Balanced (default) | Research and the planned direction together, then finished work. Training Studio also stops for the research plan first |
| Automatic draft | Finished work only, and each drawn slide deck |
| Step by step | Every existing stage |

A slide deck pauses the same way in Presentation Studio and Training Studio, at
the brand's three checkpoints: the wireframe draft of what it says, its look
(picked from the brand's rendered samples), and the finished deck. Step by step
stops at each; Balanced asks for the draft and the look in one stop, then the
deck; Automatic draft stops only at the deck and uses the brand's default look,
saying why. No stop is passed while a review or the brand's audit still finds
something grave.

Presentation Studio's direction stop includes research, the editable outline
with its wireframe draft, and the brand's rendered looks to pick from. A Blog Studio run
started in chat includes research with the outline, and the writing, independent review
and requested handoff at the final stop; a blog on the desk has no stops.
Training Studio reads the research plan before any research is run, then groups
all selected levels into one stop, **Review the first drafts**, with each deck's
wireframe draft and the brand's looks to pick from, stops at each drawn deck, then
one review of the completed documents, decks and scenarios.

### Everyday choices, Advanced, and who owns a value

First-run setup asks only the four everyday choices, in three steps: you and your
assistant, your workspace, and brand and delivery. Shared settings shows the same four
cards first, with section links (**Everyday**: Assistant, Workspace, Brand, Delivery;
**Advanced**: Models, Brand release, Research sites, Installations). A new person can
make the four choices, save, and return to Studios without opening an install control.
A studio can open one listed part directly with `view=settings&part=<part id>` in the
link's fragment, as Infographic Studio's Team library does for `workspace-part`. Any
other value is ignored, and first-run setup keeps its steps.

The Advanced parts are closed disclosures that say what they hold while closed:
**Models and reasoning** (shared model, reasoning and routing by task), **Brand skill
release**, **Research sites** and **Studio installations**. A value set in place of the
automatic one is tagged **Override** (models by task or a chosen model, a pinned release,
an installation folder you set), so an override is never hidden by the disclosure. Model
lists are read only when Models and reasoning is opened, so opening the page asks no
assistant anything.

Each part is tagged with who owns it. **Shared** values are saved once for every studio
on this computer and new work starts with them. **Project** choices are made for one
blog, presentation or training in its studio and kept with that work. Presentation
Studio's and Training Studio's Settings say the same on their Shared settings card,
with **Change shared settings** leading to this page.

After setup, the save state and **Save settings** stay in view at the foot of the
window: **All changes saved**, **Unsaved changes** while the form differs from what it
was shown, **Saving…**, then **Saved at** a time. Leaving for another view keeps typed
changes on the page and says they are not saved yet; reloading or closing the tab asks
first. A refused save, such as a form outdated by another studio's change, keeps the
typed changes and stays **Unsaved changes**. A save sends only the leaves that changed,
so overrides and values this page does not show are kept as they are. A group nobody
changed sends nothing, so a default the form fills in for a value the config lacks (a
branch, when to share, the delivery format, model routing) is never written unasked.
While the save bar shows, toasts sit above it.

### One save, and Blog Studio's own setup

Shared settings is one form: **Studio installations** is its last part, and **Save
settings** writes the shared choices and then any installation folder that changed. When
the folders are refused after the shared choices were saved, the page says so: "Your shared
settings were saved. The installation folders were not: …". Each setup step is named once,
in the numbered list. Blog Studio's own first run asks only what Blog Studio uses: no
review level, delivery format or slide previews, and their saved values are left as they
are.

### Where a run stops

Training Studio's and Presentation Studio's start forms have a stops card (**Where this
training stops**, **Where this deck stops**): the
three levels as one control, the stops the chosen level makes for this run, and a chip,
**Use this for new work in every studio**. The control sets this run's level only and
starts at the shared level the form read. With the chip on, the level is written to the
studios config, under its lock, when the run starts. Nothing on the form leaves it.

Each studio's Settings has **Where new work stops**, saved at once the same way.
Marketing Studio's onboarding page keeps its own control. A write from a form or a
Settings page that read a level another studio has since changed is refused, with
nothing written and nothing started: "Another studio changed where new work stops.
Reload the page and try again." A file that cannot be read shows Step by step, and
nothing is written to it.

Once a run has started, one line under its stages says how many steps are left, where
it next stops for you under its own level, and what it has spent so far, in dollars
only when every job reported them ("the assistant reported no cost" otherwise). Every
**Ask for changes** sheet says what is drawn again and what those steps took the last
time they ran, or that this computer has no record of what they cost.

Automatic continuation is recorded as policy acceptance, never as your personal
approval. Source scope, validation, visual review, bounded repairs, questions,
spending limits and blocking failures still apply. Publishing and sharing controls
remain explicit. Existing runs and adopted work retain their earlier review flow;
changing settings affects new work only. Conversations without a saved runner
policy continue to use their existing guidance.
