# Release notes

The newest release is first. The version being worked on is in [`VERSION`](../VERSION), and the companion skills' floors are in [`pins/companions.json`](../pins/companions.json). Each studio's own changelog has the detail.

# Marketing Studio 4.22.0

Every studio is at 4.22.0. These are the changes since 4.21.0.

- **A training made in a conversation is a saved record, never continued.** Training Studio no longer continues a training made in a conversation with the helper `training.py` ([#547](https://github.com/dbbaskette/marketing-studio/issues/547)). It is listed under **Saved earlier** as made in a conversation, and the page and `training.py status` say it is no longer continued. Its files can be read in place, and its one action is **Bring it in**, which copies it into the workspace and leaves the original as it was. What happens next depends on what it holds:
  - With nothing made yet (intake, a research plan, research), it is read-only, with **Start new work from this**, or **Start a new training** if it was only started.
  - With a teaching plan or more, it opens on the desk once brought in: **Open on the desk**, read the preview, then Apply.
  - Marked finished with nothing left to make, it keeps its finished **Open on the desk**.
  - Marked finished while a copy was never made (a Word copy, say), it opens on the desk; the copy stays not made, and History keeps the limitations it was accepted with.
  - A material written after the plan and never saved is kept as it is and not made on the desk, and History says so.
  - A stage saved and never reviewed says so, not "not started", in a conversation's training and in a saved record of the earlier runner alike.
  - One whose record cannot be read, or whose folder Bring in refuses (inside the workspace or its repository, holding the workspace, holding a symbolic link or a file or folder that cannot be read, or named as a workspace training already is), is a read-only record where it is: it says why, its files can be read, and **Start a new training** is offered.
  - From a phone on the private link, **Bring it in** is not offered: the record says it is done on the computer.
- **What to do with such a training.** Open the Training Studio page, find it under **Saved earlier**, choose **Bring it in**, then **Open on the desk**, or start new work from it. The helper's `approve`, `skip`, `research-import` and `pin`, and for such a training also `save`, `checkpoint` and `export`, change nothing and say in one sentence that Training Studio no longer continues it: bring it in on the Training Studio page, or start a new training. On a desk training, `approve`, `skip`, `research-import` and `pin` say what the desk does instead (Mark ready, Change settings, `studio desk submit`, nothing to pin), and `save`, `checkpoint` and `export` still work as before on a desk training your computer runs. `studio saved-work` says, for each saved training, whether it opens on the desk, was finished earlier, waits to be opened, is a read-only record or must be brought in first.
- **Removed from Training Studio.** The gate screen and its decisions (approve, skip, bring back, move approval to the conversation), with the routes `/api/gate`, `/api/decide` and `/api/approval`; the helper's code that continued a conversation's training; the screen-only repair round of the earlier flow; and the references `gates.md`, `intake.md` and `short-commands.md`. Training Studio's guidance now teaches the desk, so it needs Training Studio 4.22.0. Also: a saved deck outline that cannot be read no longer keeps a training's plan, guide and brief from the desk. The training opens without it, the deck is not made yet, and History says why. Every saved state of a training made in a conversation is pinned by a test over stored trees, which cannot be captured again. The shared stylesheet no longer has the styles only the gate screen used.
- **Blog Studio's manuscript editor check runs to its review.** A check with research (its plan and research, or the claims in your material) and a revision (its draft) no longer stops after its first step ([#548](https://github.com/dbbaskette/marketing-studio/issues/548); the stop was left open in 4.21.0). It runs through every step to its review, whatever the saved review level, without stopping for anyone's approval, and the editor screen says which step is under way. Each step it accepts is recorded as accepted by the check itself, with the saved review level kept and marked as not applied. The run's About card says the check accepted its own steps and names no review level. A check that 4.20.0 or 4.21.0 left stopped or waiting before its review says where it stopped, and **Start again** starts it again with its research. If the blog changes under a running check, the check stops and says to start it again; the manuscript is unchanged.
- **Blog Studio: a saved blog no longer waits on a result it cannot use.** A saved blog of the earlier flow that waits on a ready repurpose or interview result, which cannot be saved to it, can let it go: open the task, copy what you want, then **Discard this result** and confirm. The blog then opens on the desk or is read-only, as what it holds decides. Nothing else can be discarded this way. Start-up also clears a step marker left beside a run record that is missing or cannot be read, so the workspace no longer stays busy.
- **Removed from Blog Studio.** Run creation now makes only the manuscript editor's review. The earlier flow's creation modes (a new blog, from files with three angles, the point, from an outline, ideas) and their choices are gone. Also gone: the runner's angles, outline and package branches, the review level's automatic acceptance of steps, `run create`'s options (the command still refuses with the desk command), the run screen's controls for a step under way, and the review screen's ideas, angles, outline, handoff and approve parts. Saved runs of those modes still open as before.
- **Kept.** The shared review-level code (`deck_flow.PAUSES`, `pauses()`, and the automatic and balanced paths of `review_policy`) stays: Training Studio's and Presentation Studio's desk work still uses it. See [saved-work compatibility](saved-work-compatibility.md).
- **Not done yet.**
  - Desk work that an assistant drives in a conversation cannot be finished there: it gets no index, never reaches ready (nothing records the deck's coverage review or makes the Word or Google copies), and research and its plan are accepted when submitted, with no step to mark them Ready. That was so before this release; the guidance now says so, and each stage reference was walked on such work to prove what it says ([#554](https://github.com/dbbaskette/marketing-studio/issues/554)). No stage was run with a real worker.
  - On a desk training, `pin` and `skip --unavailable` worked before and now only say the desk's way. Only guidance for the earlier flow used them.
  - A training made in a conversation that cannot be brought in offers **Start a new training**, not **Start new work from this**, because its start form is read only from a training in the workspace.
  - A brought-in copy's saved record says it was saved by the earlier step-by-step flow. That is true of the copy, but it does not say it was made in a conversation.
  - Once the desk writes a material that was kept unsaved, or an outline that could not be read, the earlier bytes are kept only in git history and in the original conversation folder.
  - No browser fixture shows Blog Studio's manuscript editor screen with a stopped check; it was looked at over a throwaway fixture.

# Marketing Studio 4.21.0

Every studio is at 4.21.0. These are the changes since 4.20.0.

- **Desk work does what the earlier flow did.** The gaps found when the tests moved onto desk work are closed ([#549](https://github.com/dbbaskette/marketing-studio/issues/549)):
  - Blog Studio: a new desk blog is shared with a selected Team Hub as soon as it is made. A desk blog is published to the team as a numbered revision once it is marked as published and nothing is under way on the desk; otherwise the refusal says what is left. A blog moved to the desk is judged the same way, and a finished run opened on the desk publishes as before. When another computer takes a blog over, a desk job working on it here stops as the desk's **Stop** stops it, with its inputs kept. **Make a Google Doc** refuses a DRAFT.md changed outside the desk since the desk last wrote it, and says how to write it again.
  - Presentation Studio: in a team workspace, a deck this computer delivered is taken back and then changed, or opened, on the desk in one step, without **Take it over** first.
  - Training Studio: a desk run shares what it made with the team once everything it can draft is drafted, when the workspace shares after each decision; a paused, stopped or failed run, or one with a question, shares nothing until the next decision. A level's Yoodli layouts are written once its brief is marked ready or sent to its copies, so each names the copy to upload; until then its card says it waits for the brief. A training whose materials are all ready but which is not finished says why in the desk's words, not "Next: write the index". Set-up no longer moves the workspace while a training has a step in hand, and a stopped training no longer holds set-up or sharing back.
  - Kept on purpose: a Training Studio training keeps the computer that runs it until every material is marked Ready. One handed over before then says that nobody is running it, and a teammate is no longer told it was finished.
- **A blog moved to the desk in a team repository can be shared and published.** The shared running-step check now reads a Blog Studio blog moved to the desk by its own record. Before, it read the blog as a Presentation Studio record it could not verify and refused every share, take and publish in that repository.
- **A phone on the private link is kept from this computer's folders.** The owner's ruling: refuse folders, allow addresses ([#539](https://github.com/dbbaskette/marketing-studio/issues/539)). From a phone you can no longer change the Workspace folder, the installed skill folder or a studio installation folder, or set up Presentation Studio's or Training Studio's workspace; those are done on the computer. A brands, brand skill or team repository is taken from a phone only as an https or ssh address of another computer, never a folder or an address of the computer itself. Installed brands are listed by name, never by folder, and no failure sentence a phone is given names a folder; the deck studios' set-up, brand and upkeep answers name none either, not even inside a sentence such as the one saying a skill link is broken. Presentation Studio's and Training Studio's Settings tell a phone that set-up is changed on the computer, in place of **Change the set-up**. **Bring in** is refused from a phone, and a studio's setup page no longer takes a Gemini API key over the link. Everything else still works from a phone: the work itself, settings that name no folder, a web repository address, uploads and Google Drive folder links. On the computer nothing changes. The link no longer holds Blog Studio's Google and library actions open for up to 10 minutes: they answer at once and carry on in the background, so they take the ordinary time limit. See [what a phone can change](local-network.md#what-a-phone-can-change).
- **Small defects fixed** ([#544](https://github.com/dbbaskette/marketing-studio/issues/544)):
  - Blog Studio: a desk address opened with a fresh key opens the desk (no more "sDesk is not defined"), and a view whose page script did not load says so with **Reload the page**; the desk's arc keeps readable labels in a narrow pane; an unreadable saved record's migration preview says so in a plain sentence; the desk says "Outline in the parts list", not "the Outline tab".
  - Presentation Studio: a deck's missing research bundle is said in a sentence, without a folder path; a deck not yet on the desk lists its parts on the left, made and still to make; **Copy as new** of a deck upgraded to Redesign brings the deck it is redesigned from, with every selected change; **Bring in** refuses a folder that is, holds or lies inside the workspace, and set-up refuses a deck's folder or a folder inside the workspace in use; start-up's tidy-up of saved decks looks into at most 2,000 folders of each deck's work and sources.
  - Training Studio: a training whose records cannot be read is said in one plain sentence, named by its folder inside the workspace; **Bring in** refuses a folder that is, holds or lies inside the workspace or anywhere in its repository; the migration tests run on their own; two unused engine methods are gone.
  - Marketing Studio: the Presentation Studio bundle builder needs its brand repository named in the source config or by `--brand`, and no longer looks for an old folder beside the checkout.
  - Decided: the saved-record guard keeps answering 409 in Presentation Studio, as in Training Studio; Blog Studio's answers 400.
- **A research bundle can hold a folder path of the computer that made it.** Found, not changed here: a research bundle built from supplied documents records the full folder path of each document's intake copy as its origin, in two digested files (`research/facts.json` and `research/evidence.md`). Harness Research writes that origin and requires it when a source is selected, so the fix belongs in Harness Research; nothing in Marketing Studio changed for it ([#550](https://github.com/dbbaskette/marketing-studio/issues/550)).
- **Not done yet.**
  - A phone on the private link is still shown the folder values already saved on the computer: the shared settings' folders and any repository saved as a folder, each studio's installation and workspace folders on the home page, where Git and the other tools were found, the Document Library's folder, and each deck's or training's folder in the studios' lists. Showing them is the owner's separate decision.
  - Not rechecked or not fixed from #544: Blog Studio's library speed tests and one cleanup test that fail only while several suites run at once on one machine (no shared path or race was found), and the manuscript editor's research check stopping after its research plan.
  - Nothing was tried against real Google: exporting a Google Doc and uploading a deck from Training Studio and Presentation Studio, which refuse redirects since 4.19.0, are still to be confirmed once with a real account.

# Marketing Studio 4.20.0

Every studio is at 4.20.0. These are the changes since 4.19.0.

- **Old saved work is opened or read, never continued.** Work Blog Studio, Presentation Studio or Training Studio saved in the earlier step-by-step flow now opens as a saved record, listed apart from desk work. Work with a plan, outline or draft offers **Open on the desk**: a preview, then Apply; a failure, worker question, pause or stop it was saved with stays in History, and its step stays unfinished. Finished work keeps what it could do before. Work that waits (an interrupted opening, a step still running, another computer running it) says for what. Work with nothing made yet, and any record that cannot be read, is read-only: its files are kept and can be read, and **Start new work from this** starts again from its start form; research already done on it is not carried over. Nothing continues the earlier flow any more ([#542](https://github.com/dbbaskette/marketing-studio/issues/542)).
- **A deck started with research no longer stops a whole workspace.** The shared check for running steps now knows every record Presentation Studio and Training Studio write, so sharing, migration previews and conversation edits work beside a desk deck started with research. A record the check cannot understand still stops them, and the notice now names its folder and why ([#541](https://github.com/dbbaskette/marketing-studio/issues/541)).
- **More saved work opens on the desk.** A saved Presentation Studio deck made with parallel research, once its outline is drafted, and a deck or training saved with a worker's question unanswered after its outline or plan, now open on the desk. So do a Training Studio training saved with a failure after its plan, and a Blog Studio blog saved with outline notes the desk cannot read as sections (kept whole and shown on the desk) or with a research execution record.
- **The earlier flows' controls are gone.** Continue, Try again, Answer, gate decisions and the earlier run and gate screens; Blog Studio's develop, handoff, note, Continue without research and Apply the review's findings, and its `run submit`, `approve`, `changes`, `handoff` and `choose` commands; Presentation Studio's review levels, step note, storyboard, first-draft check and slide pictures at the outline stop; Training Studio's gate dispatch, combined review, look step and question-by-question research queue. Each studio refuses any other change to a saved record at one guard. Blog Studio's manuscript editor check works as before.
- **Not done yet.** Training Studio's conversation-guided helper commands and the gate screen they use stay, although no such training can be started any more, and Blog Studio's runner still holds creation modes no one can reach: follow-up issues retire both. Gaps in desk work found while moving tests onto it are not fixed in this release and will be filed separately.

# Marketing Studio 4.19.0

Every studio is at 4.19.0. These are the changes since 4.18.1.

- **The parts of a project down the left.** Every studio's project page lists the project's parts on the left (a blog's outline and sections, a deck's slides, a training's materials, an infographic's parts), each with its state, from one shared list. A Presentation Studio deck that is not yet on the desk has no list.
- **Upgrade a Selected changes deck in place.** A Presentation Studio deck made with Selected changes can become Redesign, keep content without starting again. Nothing is spent until you press Start on the new step, which says what the redesign does and how long it takes; the changes you made are kept, and revisions already delivered stay delivered.
- **Old saved work opens more often.** A Presentation Studio deck paused in the old step-by-step flow now opens on the desk, and one whose record cannot be read opens as a read-only record with its files. Every saved state of the old flows in Blog Studio, Presentation Studio and Training Studio is now pinned by a test. Known limit: one Presentation Studio record the shared running-step check refuses, such as a desk deck started with research, stops sharing, migration previews and conversation edits for its whole workspace ([#541](https://github.com/dbbaskette/marketing-studio/issues/541); lifted in 4.20.0).
- **One look and fewer waits.** Since 4.18.1: one look for Marketing Studio and all four studios, a command palette that finds your work, questions asked in place, one main action per view, pages that stop polling while hidden, a home page that answers while a studio starts, companion checks that ask once, Brand setup in one pass (PDF brand books read, document templates, Rebrand a Google file), research and finished work kept in the Document Library with **Continue in another studio**, and Infographic Studio's long actions in the background with **Stop**.
- **Safer and smaller underneath.** Blog Studio, Presentation Studio and Training Studio send Google requests through one shared transport; Presentation Studio and Training Studio refuse redirects and any destination they do not use, and Blog Studio refuses a Word file whose inner XML declares a DOCTYPE or entity. Every PDF, Word and HTML reader is shared. Blog Studio's unused reference toolkit is gone, so a release has two Blog Studio archives, not three.

# Marketing Studio 4.18.1

Every studio is at 4.18.1. These are the changes since 4.18.0.

- **Learner tasks carried through delivery.** A training's assessed learner tasks, shared cases and job aids reach every material built from its teaching plan.
- **A one-page job aid for Infographic Studio.** An approved teaching plan's **One-page job aid** can be chosen in Infographic Studio's **Import selected studio material**.
- Research triage keeps a qualification that changes a decision, and Presentation Studio's repair and review steps keep attribution guidance.

# Marketing Studio 4.18.0

Every studio is at 4.18.0. These are the changes since 4.17.1.

- **Technical training that rehearses.** Training Studio plans technical workshops and CLI labs around what learners do: local configuration, a check or a conditional decision taught as such, and instructor preflight for what cannot be assumed.
- A paired teaching benchmark, for comparing technical trainings, is described in [Training Studio's teaching benchmark](../studios/training/docs/teaching-benchmark.md).

# Marketing Studio 4.17.1

Every studio is at 4.17.1. These are the changes since 4.17.0.

- Marketing Studio previews brands in batches, and research searches passages in batches, so both read less.
- A provider timeout offers a retry, and the Team Hub guide is back in Training Studio's navigation.

# Marketing Studio 4.17.0

Every studio is at 4.17.0, aligned for the first time. Versions 4.13 to 4.16 of the suite were never released; their work is in this release. These are the changes since 4.12.0.

- **Nothing pinned to one installed version.** Studios, Harness Research, Harness Slides and the brand skill are reached through a stable `current` link and installed and updated from their repositories' `main`, with oldest-accepted versions in [`pins/companions.json`](../pins/companions.json). The brand skill's release setting is gone. Training Studio and Presentation Studio update themselves from `main`.
- **No spending limits.** Nothing stops, pauses or warns for cost; reported cost stays as information. Assistant steps get more time, and Blog Studio's step time limit is gone.
- **Desks rebuilt as workbenches** with a shared shell: one Brief, Plan, Make, Ship arc, one card for what waits for you, and a command palette.
- **More ways in.** **Copy as new** for a training or deck, a whole folder of sources, every link in an uploaded file, up to 1,000 links per research run with Harness Research 1.2.0, the Document Library keeping files of any type, and **Document graphics** in Shared settings. Training Studio follows your outline and documents, plans as an instructor would teach and draws its own charts; Blog Studio writes solution briefs; Training Studio can rebrand a finished deck with **Change brand**.
- Studio READMEs were rebuilt around a first project, with illustrated guides.

# Marketing Studio 4.12.0

Marketing Studio 4.12.0 ships Presentation Studio 4.15.0 and Training Studio 4.14.0 (Blog Studio 4.10.1 and Infographic Studio 0.5.0 unchanged). These are the changes since 4.11.1.

- Finished research sections can be read before the final check, and concerns you queue are kept privately until you apply them.
- The time to the first readable section is reported apart from the time to the checked result.

# Marketing Studio 4.11.1

Marketing Studio 4.11.1 ships Presentation Studio 4.14.1 and Training Studio 4.13.1. These are the changes since 4.11.0.

- An idle desk checks a small change signal before reading its content again; focus and reconnecting catch up at once.
- Quick scan choices say more plainly what they do.

# Marketing Studio 4.11.0

Marketing Studio 4.11.0 ships Presentation Studio 4.14.0, Training Studio 4.13.0 and Infographic Studio 0.5.0. These are the changes since 4.10.0.

- An unfinished start form is kept across reloads, in Infographic Studio too.
- Slide-text review shows one slide at a time, and corrections are kept across reloads without starting work.

# Marketing Studio 4.10.0

Marketing Studio 4.10.0 ships Infographic Studio 0.4.0. These are the changes since 4.9.0.

- Marketing Studio's home refreshes pending work, and a preview that fails says why and how to recover.
- Infographic Studio keeps its renderer guidance when an approved file is recovered.

# Marketing Studio 4.9.0

These are the changes since 4.8.0.

- Brands are written and finished in the brands repository set in Shared settings.

# Marketing Studio 4.8.0

Marketing Studio 4.8.0 ships Presentation Studio 4.13.0 and Training Studio 4.12.0. These are the changes since 4.7.1.

- New decks and trainings warned and carried on at a project spending amount instead of stopping. (Spending limits were removed altogether in 4.17.0.)

# Marketing Studio 4.7.1

These are the changes since 4.7.0.

- `marketing-studio` commands reuse a studio link that is already running instead of starting another.

# Marketing Studio 4.7.0

Marketing Studio 4.7.0 ships Blog Studio 4.10.1, Presentation Studio 4.12.1, Training Studio 4.11.1 and Infographic Studio 0.3.1. These are the changes since 4.6.0.

- **See what the assistant is doing.** Every studio shows the assistant's work as it happens and keeps an Activity log for each project.
- **Approve the plan before detailed research.** Training Studio starts with a Quick scan outline you approve, and Presentation Studio with a slide story you approve. A new deck or training can be left half filled in and resumed.
- **Research that keeps its parts.** Section contributions are kept across retries, and a change to the sources previews which sections it affects before anything is redone. Local build steps recover, and saved work resumes where it was.
- **Settings.** A model and reasoning level for each kind of work, and a brands repository fetched only when you ask. Google Slides sources are read through Google Drive, and each studio README shows its workflow as a diagram.

# Marketing Studio 4.6.0

Marketing Studio 4.6.0 ships Blog Studio 4.10.0, Presentation Studio 4.9.0, Training Studio 4.8.0 and, for the first time, Infographic Studio 0.3.0, which is not yet signed off. Installs pin Harness Research 1.1.0 and Harness Slides 0.16.0, and Tanzu Brand 0.14.1 was tested. These are the changes since 4.5.0.

- **An editing desk in every studio.** New blogs, decks and trainings are made on an editing desk: a note rewrites only the part it names, History keeps earlier versions to compare and restore, and Finishing's tools propose changes you apply or skip. Presentation Studio's Slides tab reviews one slide at a time, and Training Studio's desk holds each level's materials. You can also ask your assistant to work on a desk in chat; a focused request stays focused and starts no other assistant.
- **Saved work keeps its path.** Work started step by step continues as before. Eligible unfinished work moves to the desk only after a preview you confirm, keeping its records, decisions and History. The shared **Where new work stops** setting is gone; existing runs keep their review level.
- **Blog Studio: a GEO review and reader aids.** Tick **Include a GEO review** on a new blog, or choose **Run GEO review** under Before publishing, for located proposals that make passages easier to reuse in AI search, such as a claim missing its date, version or unit, or a procedure that wants numbered steps. Finishing's **Reader aids and AI search** adds an FAQ, key takeaways, a comparison table, quotes checked against their sources, alt text and a definition-style opening, each previewed first. A detail only the author knows is asked for, never invented, and nothing is promised to earn citations or rankings.
- **Blog Studio: a GEO report for a published post.** **Get a GEO report for a published post** reads a live post's link and makes a report: what already works, ranked changes marked inline with their reasons, and **Page access** checks such as noindex, robots.txt for search crawlers, structured data, byline and dates. Download it as HTML or Markdown, make a Google Doc with each change as a suggestion, or **Edit this post on the desk**. **Link to a published post** also brings a live post to the desk for a GEO review.
- **Blog Studio: posts built by scripts.** When a page fetches its article with scripts, **Ask Codex to find the post's text** (or Claude Code) asks your assistant, with no tools or web access, where the text comes from on the same site. Blog Studio reads that address itself under the usual limits, and takes one second look within the same 3 minutes when the first answer finds no text. A recipe that works is kept for that site on this computer.
- **Blog Studio: also new.** **Check spelling and grammar** reviewed in your text, with optional more human-sounding wording; Copy edit in Finishing; the Google Doc round trip finished on the page with **Bring accepted changes**; other people's pending Doc suggestions shown on the desk; an SEO meta description from Repurpose; and a plain message when the assistant cannot reach its service from your network.
- **The Document Library.** Marketing Studio's new **Library** screen keeps text, Markdown, HTML, Word and PDF uploads and finished work on this computer: finished blogs, delivered decks with their matching PDF, ready learner guides and briefs, and approved infographics. **Add from library** copies a chosen revision into one project, and a newer revision is taken only with **Use revision N**. Uploads offer **Keep in library** or **Only this project**; in Blog Studio, **Keep a copy in the Document Library** or **Only this blog**. **Add existing work** previews older finished work before adding it, and **Remove from library** hides a document without deleting it. The library is kept in `library/` under your work folder, normally `~/Studios/library`. Choosing documents starts no research and shares nothing with your team.
- **Training Studio material review.** A material opens to read as learners receive it, with **Edit** for its parts and **Copy text** for a section. **Mark this level ready** lists each material as opened or not and changes nothing until you confirm, and **Undo** and **Return to draft** reverse it. Home, Trainings, Status and the desk show one standing for each training. A training kept locally can make a Google Doc of a guide or brief when you ask.
- **Presentation Studio.** New deck asks what the deck starts from and its goal, then lists what happens after Start. **Approve text & design deck** never drops a change you typed, and slide text can be corrected in place. The Delivered card keeps a receipt for every revision.
- **Shorter setup and clear ownership.** Shared settings lead with four everyday choices; models, the brand skill release, research sites and installations are under **Advanced**. The save state stays in view, and Shared, Override and Project tags say where each value is set. When another tab or studio saved first, the notice names the setting and offers **Load newer settings**; nothing is written from an outdated form. Studio cards say **Can open**, **Needs setup**, **Not checked** or **Not installed**, with one recovery action, and checking starts no assistant, sign-in or paid work.
- **Phone access.** With phone access on, the computer's home shows a QR code for the private link, drawn on the computer with nothing fetched. A studio opened on the computer stays at `127.0.0.1`; only one opened from the phone goes through the network bridge, which now accepts each studio's own upload sizes. Training Studio's materials and Infographic Studio work better on a phone.
- **Infographic Studio 0.3.0, not signed off.** The fourth studio turns supplied documents, notes, links or selected CSV into one branded page with source-backed story choices, editable labels and charts, a visual editor with readable history, exact-revision approval, and PNG, PDF, editable SVG and accessible-text exports, with optional Codex or Gemini artwork. Its editor, exports and provider adapters are implemented. Live Codex/Gemini image acceptance, artwork review and first-release sign-off ([#152](https://github.com/dbbaskette/marketing-studio/issues/152), [#223](https://github.com/dbbaskette/marketing-studio/issues/223), [#224](https://github.com/dbbaskette/marketing-studio/issues/224)) are still pending, and a fake-provider test is not proof of live provider access. Its initial acceptance target is macOS on Apple Silicon. See [first-release readiness](infographic-first-release-readiness.md).
- **Companions.** Installs use Harness Research 1.1.0 (up from 1.0.1) and Harness Slides 0.16.0, each at an exact commit and source checksum. Decks need a brand skill at 0.14.0 or newer, and this release was tested with Tanzu Brand 0.14.1. Marketing Studio never installs the brand skill.

Download `marketing-studio-installer.zip` for the whole suite, now with Infographic Studio, or one studio's installer ZIP. Each has a `.sha256` file for checking the download. Unzip it, then run `bash install.sh` in the unpacked folder, or open `installer/Install Marketing Studio.command` on macOS. Close running studios before you update. Your existing workspaces and settings are kept.

Signing in to an assistant, your organisation's brands and fonts, and optional Google setup are still your choices. Installing or opening a studio starts no provider job.

# Marketing Studio 4.5.0

Marketing Studio 4.5.0 ships Blog Studio 4.7.0, Presentation Studio 4.5.0 and Training Studio 4.5.0, with Harness Research 1.0.1 pinned and Tanzu Brand 0.14.1 tested. These are the changes since 4.0.0.

- **Your team's repository, connected.** Home says where each studio's work lives: connected to a repository and branch, local Git on this computer, or not connected, with a **Connect** action. A shared repository set in Marketing Studio now reaches studios that already have a workspace.
- **One team library.** Blog Studio keeps finished blogs, added files, lists of links and Google Docs in one library, each with a role, an author and a kind of post. A list of links by many authors is sorted by each post's own byline.
- **Voices and styles.** Learn a voice for any author, so ghostwriting has one voice for each person, and start from eight ready-made styles for technical writing. A voice can be learned from a file of links to an author's posts, from up to twenty samples. Voices and styles opens from Blog Studio's Home and sidebar.
- **Say what each file is for.** Each upload is marked as facts, an example of the kind of post, or approved messaging. Examples shape a post but never supply its facts. **I know the point** starts from the point you already have, and you choose the voice as you go. Write from a brief takes every file at once, and a Google Doc is read tab by tab.
- **The authoring workflow review, Phases 1 to 5.** Research can finish, and a failure says what to do next. Each thing has one name, and **Where this run stops** sets how often a run stops for you, saved once for every studio. Research stops show the brief, the independent check, the gaps and the findings for each question, along with what a change would cost. A training, deck or blog can be finished on its page: download it, bring back your edits, apply review findings and approve the version shown. Harness Slides, Harness Research and the brand skill are now fully used.
- **Research checks read the originals.** The independent check reads a supplied Google Doc, PDF or Word file as it is, so supplied material no longer fails the check again and again.
- **Research from your documents, your sites and/or the public web**, in every studio. Your sites are listed in Shared settings. Each page research saves is checked against them, redirects included, and a site can be added for a single piece of work.
- **Announcements that read like announcements.** Blog Studio writes approved messaging in the product's own voice and keeps source notes and open questions out of the text.
- **Delete from the lists.** Decks, trainings and blogs can be deleted from the lists and Home cards that show them, with each studio's usual confirmation.
- **Also since 4.0.0:** one shared Golden Gate look on every studio page; `marketing-studio start`, `stop` and `restart`; installer diagnostics and repository sync; slide text you can change after a deck is built; blogs finished, published, deleted and restored from the page; a blog written from your uploaded files, with three angles to pick from; and pages that work better on a phone.
- **Companions.** Installs use Harness Research 1.0.1 and Harness Slides 0.16.0, each at an exact commit and source checksum. Decks need a brand skill at 0.14.0 or newer, and this release was tested with Tanzu Brand 0.14.1. Marketing Studio never installs the brand skill.

Download `marketing-studio-installer.zip` for the whole suite, or one studio's installer ZIP. Each has a `.sha256` file for checking the download. Unzip it, then run `bash install.sh` in the unpacked folder, or open `installer/Install Marketing Studio.command` on macOS. Close running studios before you update. Your existing workspaces and settings are kept.

Signing in to an assistant, your organisation's brands and fonts, and optional Google setup are still your choices. Installing starts no provider job.
