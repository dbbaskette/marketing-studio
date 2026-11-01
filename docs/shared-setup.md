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
Marketing Studio's **Library** screen or one kept with **Keep in library**, a finished
or published blog, a delivered deck, an infographic's approved files, or a Training
Studio guide or brief marked ready. On the first one, the resolved folder is saved through the config's adjacent
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
- Finished work with a saved PDF also keeps `content.pdf`, the PDF its studio checked.

Each revision is written whole into a hidden folder and then renamed into place.
Every write holds `.library.lock` (an interprocess `flock`). The catalog in
`.state/catalog.json` is rebuilt from the records whenever it is stale or damaged.
Each studio's browsing filters are kept in `.state/filters.json`; they are filters
only, never a selection. A deck's folder is a slug of its title, so a delivered deck's
key adds a random part made once for that deck. Two workspaces with decks of the same
title, or a deck deleted and made again, are separate documents. A blog's ID already
ends in a random part, so `blog:<id>` is unique. A saved library folder that is gone,
such as on a drive that is not connected, is reported and not made again.

**The Library screen.** Marketing Studio's **Library** lists documents first, with
**Add documents** as the toolbar's one filled action and **Add existing work** beside
the lede. **Add existing work** stays a plain button with a one-line hint until
something has been added from a studio's workspace, then becomes quiet. Both open a
sheet; Close and Escape return to the button that opened it. On a phone only the
search shows, with a **Filters** button that opens Type, From, Origin, Status and
Author and counts those set, remembered filters included. Every studio's **Add from
library** sheet has the same Filters button. Each row has one action, **Preview**,
which opens the document just below its row. The preview holds every download
(Markdown, the original and a saved PDF) and, on the Library screen only, **Remove
from library**. **Close preview** returns focus to that row's Preview.

**Add documents, file by file.** Each chosen file is added on its own and reported
by name: **Added**, **Already there** or **Not added**, with why (not a text,
Markdown, HTML, Word or PDF file; larger than 8 MB; empty). One refusal stops
nothing. A file keeps its operation ID while the page is open, and what was added
leaves the selection, so **Add to library** again tries only what was refused. The
same file uploaded again (its name, bytes, title and studio) is the document already
kept, even from another page. The page always asks the library, so a file removed
since is shown again. When that document's kept files changed or went missing ("Upload
it again"), uploading the file keeps a whole new revision of the same document instead.

**Remove from library.** It hides a document: `documents/<id>/document.json` says
so, written atomically under the library's lock. A hidden document is left out of
browsing, of every studio's **Add from library**, of **Select all matching** and of
**Update available**, and a new pin of it is refused. Nothing is deleted: every
revision stays, projects that pinned it keep their copy and keep working, and no
studio workspace is read or changed. The Library screen's **Show hidden** lists it
again with **Restore to library**. Uploading the same file again restores it too.
Finishing, delivering or adding existing work again keeps it hidden until it is
restored.

Every file is checked against its hash before it is previewed, downloaded or
pinned, and a link, a missing file or a changed file is refused. Some files can't
be added as context until their text is supplied: an image-only PDF is marked
**Needs text**, and an unreadable file is marked **Cannot be read**. Nothing is
read with OCR, a model or the network.

| Content | Kept |
| --- | --- |
| Upload | Original bytes, plus Markdown when its text can be read |
| Finished or published blog | Its Markdown, under `blog:<blog id>` |
| Delivered deck | Slide-ordered outline Markdown, under a key made once per deck (`presentation:<folder>-<random>`, kept in its local `sources/library.json`). Also `content.pdf`, the PDF Harness Slides rendered of the delivered deck in its last whole-deck preview, kept only when it still matches. **PDF saved** then. Otherwise the PDF is recorded as **needs export**, with why. |
| A file added on the Presentation Studio desk with **Keep in library** | Kept as an upload from Presentation Studio, beside the deck's own copy in `sources/supplied/`. **Only this project** keeps the deck's copy only. |
| Approved infographic | The approved export's accessible text (`page.txt`) as Markdown and its `page.pdf` as `content.pdf`, under `infographic:<workspace owner>-<infographic id>`. Only the approved, visually checked current revision is kept. |
| Training guide or brief marked ready | Its Markdown as learners read it, without coverage notes, under `training:<folder>-<id>.<material>`, where the ID is made from the folder and the run's recorded start, so a lost `sources/library.json` finds the same documents again. Marking ready in a conversation keeps it too. Decks are not kept until Training Studio can export a PDF. |
| Training Studio upload kept with **Keep in library** | As any upload, from Training Studio, from the documents card, **Add a source**, or the New training sheet's source editor once it read the file. The same file sent again is the same document |

**Choosing context.** **Add from library** pins chosen revisions into one project,
after checking every one of them first:

- **Presentation Studio** copies each revision into the deck's `sources/supplied/`
  as an ordinary supplied document, with `library` naming the ID, revision and
  Markdown hash. The deck's research, outline and words jobs read it within the
  existing 40-document and 8 MB limits.
- **Blog Studio** makes each revision a file uploaded for that blog (material) with
  the chosen role. An example stays an example. These files never enter the team
  library or the Team Hub.
- **Infographic Studio** captures each revision as a `handoff` source through the
  same capture boundary as selected studio material, with `provenance.library`
  naming the ID, revision and hashes. The Markdown is the source text and an
  upload's original is kept beside it. All chosen documents land in one new
  revision of the infographic. As with any source change, the facts, story and page
  built from the earlier sources are cleared, and nothing is approved. Team sharing
  sends a source only when it is chosen in Share.
- **Training Studio** copies each revision into the training's `sources/supplied/`
  as one of its documents, read only by its research. While the training waits for
  its documents, a pinned one is read with the rest. After the research is planned it
  is listed under `documents.later` and read only by **Update the research**, which is
  priced first. A training whose research does not read documents refuses it: pinning
  never widens where research looks.

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
| Removed from library (hidden) | The project keeps reading its pinned copy; Update available is not offered (Infographic Studio says it was removed), and adding it again is refused until it is restored |
| Unreadable, changed or missing revision | Refused with why, and nothing changes |
| Finish, publish or deliver again with the same text | Same document and revision, and no new revision |
| A library save fails after delivery | Recorded in the deck's local `sources/library.json`. **Keep in library again** retries from `deliver.json` and this computer's files, with no upload, no render and no job. |
| A delivered deck's PDF is missing, changed or of another deck | Its Markdown is kept and the PDF stays **needs export**, with why. **PDF saved** is never shown |
| **Keep in library** fails for a file added on the Presentation Studio desk | The deck keeps the source, and the card says the library did not keep it |
| A library save fails after an infographic's approved files are prepared | The approval and files stand. Recorded in the infographic's `jobs/library.json`; **Keep in library again** retries from the saved export, with no render and no provider |
| An infographic changes after approval | Its earlier approved files are not kept again; approve the current revision first |
| A job is running on the deck (the chain draws, or a desk job runs) | Add from library and Use revision N are refused until it ends; the job keeps the sources it started with |
| Work is running on an infographic (a page action, an image request pending or uncertain, or research) | Add from library and Use revision N are refused until it ends |
| An infographic has facts, a story, a page or an approval | Add from library, Use revision N and every other source change say what will be cleared and ask first |
| An infographic's own approved export, in its Add from library | Shown as unavailable ("This infographic") and refused by the server: its page cannot be a source for its own facts |
| A chosen revision has extraction gaps (Infographic Studio) | Refused until the person confirms using only its readable text; the gaps stay on the source |
| A step is being worked on in a training (a worker, or a desk change under way) | Add from library and Use revision N are refused until it ends |
| A Training Studio guide or brief's library save fails after Mark ready | It stays Ready. The failure is recorded in the training's local `sources/library.json`, and **Keep in library again** retries with no job. Its owner is offered the retry in a conversation too; a teammate only reads the state |
| A Training Studio guide or brief returned to draft (an edit, **Undo** or **Return to draft**) | The library keeps the revision it has; nothing is removed. The card says the library keeps revision N until it is marked ready again, and marking the same words ready again adds no revision |
| A Training Studio upload's library save fails | The training keeps its document; **Keep in library again** keeps it from the training's own copy |
| An upload kept with **Keep in library** that the library refuses | The project keeps its document, and the page says the library did not keep it |
| Use selected is still landing | The sheet's Cancel, Close and Escape wait |
| A newer revision, in Blog Studio | The desk source says Update available; **Use revision N** gives the blog's file a new source revision and the blog pins it. Refused while a desk job runs |

**Keep in library at upload.** Blog Studio's file picker offers **Keep in library**
(the default) or **Only this blog**. Keep in library sends `document_library: true`
with the upload. Once every file is saved, each file sent from this computer is also
kept with `add_upload` (studio `blog`, an operation ID derived from the upload's), and
the file's row says `kept` or `failed` with why. The file's own record and sharing are
unchanged. Links, Google Docs and LinkedIn exports are not kept. Its operation ID comes
from the file's name, bytes and title, as Presentation Studio's and Training Studio's do,
so the same file uploaded again is kept once. The team library page's Upload dialog and
voice or style sample uploads deliberately offer no Keep in library: they feed the team
library and voice learning, not one project's sources.

**Add existing work to library.** `document_library/adopt.py` previews and confirms an
import from the workspace each studio remembers (`marketing_studio/workspaces.py`).
The Library screen calls `/api/library-existing` for the preview and
`/api/library-adopt` with the preview's `signature` to confirm. The preview writes
nothing and does not make the library. The confirm scans again and refuses, adding
nothing, unless what it would add still matches the signature. Each item is kept with
`Library.adopt`, found again by its key, so adding again adds nothing and a changed
title, text, original or saved PDF adds a revision. A failure is reported per item; the
rest are added. No folder other than a remembered workspace is read, no studio is
started, and no workspace file is written, moved or regenerated. Every adapter reads
the studio's own files without importing the studio, offers only finished work, and uses
the studio's own library key, so finishing, delivering or marking the same work ready
later in the studio reuses the document it was added as.

A PDF is added only when the adapter checked it against the exact revision it came
from; otherwise the item is added as Markdown and the preview says why. Work the
library already keeps with a PDF is shown as already there, never added again without
it.

Blog Studio's legacy adapter, `document_library/blog_existing.py`, reads only team
library records on this computer: `sources/<id>/` in a plain writing folder, or
`.shared/references/<id>/` in a team workspace. Every read is bounded, refuses links
and checks the record's hashes.

| Blog Studio record | Library document |
| --- | --- |
| Finished or published blog (`origin_kind` written-here) | Blog, Created here, under `blog:<blog id>`: the key Finish and publish already use |
| Imported post | Blog, Imported, under `blog:reference.<source id>` |
| Upload, link, Google Doc, voice or style sample, other reference | Uploaded document, with its origin, under `blog:reference.<source id>` |
| One blog's own file (material), a Team Hub snapshot, a copy taken from the library | Left out |
| Text or original that does not match its record, a link, no text and no file | Left out, and said in the preview |
| Retired in the team library, or a record of a shape Blog Studio does not save | Left out, and said in the preview; one odd record never stops the rest |
| A file Keep in library already kept at upload (same original bytes) | Already in the library; not added again |
| An item only the Team Hub holds | Not read; the preview says so |

Each revision records `native`: the source ID and revision, purposes and role, kind of
post, author and, for a finished blog, the blog's voice and style pins. An original
file is kept when it is a supported type of at most 8 MB that matches its hash; a
record with no readable text is kept as **Needs text**.

| Studio and what is offered | Library document and key | PDF |
| --- | --- | --- |
| Presentation Studio (`presentation_existing.py`): a delivered deck (`deliver.json`) in `<workspace>/<deck>/` | Presentation, Created here: the slide Markdown (`outline.md`), under the key in the deck's `sources/library.json`, or the one Deliver makes from the deck's folder and `run.json`'s `created` | The `deck.pdf` Harness Slides rendered of exactly the delivered deck, checked as Deliver checks it (`deck_sha256`, the last build round, `preview.json`, its `deck.pptx` and the PDF's recorded hash). Otherwise none, with why: drawn again, delivered elsewhere, Selected changes, or changed |
| Training Studio (`training_existing.py`): a learner guide or brief the person marked ready, while the file is that version and nothing it was built from changed | Training material, Created here: the text as learners read it (no coverage notes), under `training:<folder>-<part>.<material>`: the key in `sources/library.json`, or the one Mark ready makes from the training's folder and its run's start | None: Training Studio keeps no PDF of a guide or brief |
| Infographic Studio (`infographic_existing.py`): the approved, visually reviewed export of the current revision, with its sources intact | Infographic, Created here: the export's `page.txt`, under `infographic:<owner[:12]>-<id>` | `page.pdf` when it matches the hash in the export's manifest; otherwise none, with why |

Left out of every studio: drafts and unfinished work (counted in the preview), and
anything whose records the studio itself could not open, each said. A deck with no
recorded key and no `created`, or a training worked on only in a conversation, is left
out and said: Keep in library in the studio keeps it. Each revision records `native`:
the studio's own ID for the work, its delivery, material or export, and its revision.

Presentation Studio's Deliver makes a deck's key the same way when `sources/library.json`
has none, so a deck added here and delivered again later is one library document.

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

First-run setup is one column: the toolbar, any notice and the form share their edges.
A value a step cannot use, such as a shared repository with no address, is shown at its
field, which is marked invalid and takes focus. Each step that continues is remembered in
that browser tab, so a reload resumes at the step the person left. The last step is
resumed only when the configuration holds a workspace.

### Problems, conflicts and long actions

A problem notice belongs to the screen that raised it. It clears when the person moves
to another screen or the action next succeeds, and its **Dismiss** button clears it by
hand. The notice is announced once.

Saving checks every value the form changes against the configuration the form was shown.
When another Marketing Studio tab, or a studio, saved a different value for the same
setting meanwhile, nothing is written. The notice names the setting, for example "“Your
name” was changed in another tab or studio while this page was open, so nothing was
saved", and offers **Load newer settings**. That reads the configuration again and keeps
the person's edits to every value nobody else changed. Each value both changed shows the
saved value and the person's own, with **Use the saved value**, and Save stays pending.
The next save sends the newer values as what it was shown, so it is checked again under
the lock. Unrelated values in the file are never touched. The refusal also carries the
conflicting fields, as dotted paths such as `person.name`, under `conflict.fields`.

**Save settings** and **Check computer** stay focusable while they work. Each is marked
`aria-disabled`, says "Saving…" or "Checking…", and ignores another press. Focus stays
on the button, or moves to the results heading when the check was started from another
screen.

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
