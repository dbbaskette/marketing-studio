# Changelog

Unreleased: companion checks catch broken installs, and research helpers stop. A Harness Research or Harness Slides folder whose `package.json` is missing or broken is now offered again rather than left alone, and a prerelease such as 1.3.1-alpha.1 no longer meets a 1.3.1 floor. The check after a companion's installer runs accepts its `SKILL.md` with other line endings or trailing spaces, and still fails on different or missing words. The oldest Harness Slides a deck takes is read from the companion pins, not written again in the runner. Research looks for Harness Research in `~/.cursor/skills` too, and the check of a research packet registers all its sources in one helper call. A helper command that research runs itself is ended, with what it started, when the research is stopped.

Unreleased: **Change brand**, **Make a rebranded copy** finds rebranding skills where every studio looks for a brand skill, now including each installer's folder and the Cursor skills folder, runs each with the Python its own setup made, and reads the brands from the **Brands repository** in Shared settings. Decks' brand commands read that repository too, without waiting for **Get brands** ([#505](https://github.com/dbbaskette/marketing-studio/issues/505)).

Unreleased: Training Studio updates itself from `main`, not from release tags. Once a day it compares the commit it was installed from with where `main` is in its repository, and **Upgrade** installs `main` when they differ; no tag is read or waited for. The version is only a label: "A newer Training Studio is available (4.16.0 → 4.17.0)", or `main`'s commit when the version did not change. The installer keeps the commit each version came from, and a copy installed before this, whose commit is not known, is offered `main` once. Everything else stays as it was: the trusted repository, the check of what is fetched (now also that `main` is still at the commit you were shown), no hooks, the refusal while a training works, the install beside the running one, one version kept behind `current`, rollback and offline installs. After **Restart**, the page waits for the copy it installed, so it comes back even when the version is the same. The brand skill's release setting is gone from Settings: the brand skill is installed and updated from its repository's `main`. A release saved by an older version still loads and is not read.

Unreleased: nothing is pinned to one installed version any more, and old version folders can be deleted. Training Studio, Harness Research, Harness Slides and Harness Brand are each reached through their stable `current` link: an update keeps one version, and a training, a deck job or a setting saved before it goes on with the new one. Research started on an earlier Harness Research continues on the installed one, never asking to restore the old version, and its kept areas, section drafts and passed review stay kept, since what decides whether research is current names no version and no digest. `training.py pin` records only the task (`--runtime` is accepted and ignored), and a deck's slide guidance is resumed with the runtime each resume names; a notice that it started on another version is shown in the activity log. A brand chosen in Settings that named a removed version folder is found again by itself. Harness Research and Harness Slides are installed and updated from their `main` branch, with 1.3.1 and 0.19.0 the oldest accepted; **Update the skills** offers `main` again once it moves. The brand skill is installed from its repository's `main` too: there is no release to choose. Guidance that names no `--runtime` needs Training Studio 4.16.0.

Unreleased: the Document Library keeps a file of any type. **Keep in library** now works for every upload, PowerPoint (.pptx) and Excel (.xlsx) files included, whose text the library reads so they can be chosen with **Add from library**. A file the library has no reader for, such as a picture or an older .doc, is kept as it is and marked **Kept as a file**: it is listed with its name, type and size, can be downloaded and removed, and is not offered as a source. Libraries made before open unchanged.

Unreleased: a whole folder can be added as sources. Where a new training's sources are chosen, and in **What research reads**, **Add a folder** takes a folder path on this computer or a Google Drive folder link and adds every document in it and its subfolders: PDF, Word, PowerPoint, Excel, text, Markdown and HTML files, and Google Docs, Google Slides and Google Sheets (every sheet). The page says how many were added and lists each one skipped with the reason. One add takes up to 200 documents, and a request now holds up to 400 files and pasted texts (was 40). PowerPoint (.pptx) and Excel (.xlsx) files can also be uploaded; the Document Library does not keep those two types and says so. In a conversation, `studio desk create` takes the same folder as `folder` and keeps up to 40 of its documents as the training's own, listing what it added and skipped; only a Google Drive folder uses the network. This needs Training Studio 4.15.0.

Unreleased: a training built from your documents keeps their specifics, and its deck is drawn to be looked at. The writers of the blueprint and of what a deck says can now search and read the documents you gave, as research already could, so a key point and a slide carry the figure, the name or the price your document gives and not a summary of it. A fact that only your own document states is taught as `[stated]`, with the document named in the notes. What a deck says is written so that it can be drawn: a relation for every slide, short parts for a diagram, a figure as a label, and like slides in one shape. The design proposes a drawing for every content slide, an icon from the brand's library for each thing a slide names, one large element and the deck's colors by what they mean, and keeps direct text for a question, a quotation or a single statement. Whoever draws a section is told the same, and the review counts a title over rows of sentences, things named with no icon and a slide with nothing large to look at as findings.

Unreleased: a training is planned and its deck written as an instructor would teach it. The blueprint now names the one task learners leave able to do and one realistic scenario the whole class is built around, and gives each module a hook, an activity with its output and a good answer, and a question for the room. The deck opens on that scenario, puts examples on the slides, shows learners what to do on each activity slide, and ends with something to take away. Speaker notes for a live deck are the instructor's script: what to say, the example, what to ask and listen for, the mistake to watch for, how to run the activity, and the line that leads to the next slide. This applies to blueprints and decks written from now on.

Unreleased: a deck waiting for a picture can **Carry on without it**. Beside Add the picture, this draws the slide with no picture, in the brand's own layout, and the deck's list of pictures shows it as **Left out, as you asked**. You can still add the picture later. A deck also never asks you for the brand's own cover, section or closing layout: a picture a design calls supplied on one of those slides is shown as **Comes with the brand**, and the slide is drawn from the brand's template. A deck already waiting only for one shows **Carry on**. The deck's designer is told not to name the brand's templates, layouts, backgrounds or logos as pictures.

Unreleased: a deck draws its own charts. A slide whose approved design names a chart no longer stops the deck to ask you for a picture of it: the section is drawn with a real, editable chart made from the numbers the deck already has, taken from the slide's words, the design and the sources, and never estimated. Where the numbers are not given, the comparison is shown as a table or text and the hand-in says so. The deck's list of pictures shows such a chart as **Drawn from its numbers**. A deck already waiting for a chart shows **Carry on** in place of Add the picture. Screenshots and supplied pictures are still yours to add.

Unreleased: **Copy as new**, on Home and on the Trainings list. Beside a training's Open is a way to start another like it: the start form opens filled in with its topic, audience, levels, materials, deck choices, research questions and where research may search, and with its documents already added, including those added on the desk after it started. Change anything, such as what it should teach, then Start: it is researched and written again as a new training, and the one copied is only read. A document that is not on this computer is named, to add again. A document from the Document Library comes as the revision the training kept.

Unreleased: installing or updating a companion skill brings its newest release. Once you agree, Harness Research and Harness Slides are looked up in their own repositories and installed at their newest stable release, checked file for file, instead of the version this Training Studio was pinned to. The pinned version is still what is installed when the newest cannot be looked up. Also, a deck the runner stopped itself, such as one whose brand changed, now offers **Review the slide text** and **Finish without the deck** as a failed one does.

Unreleased: rebranding a deck as a copy follows Harness Brand 1.1. The brand skills (`tanzu-brand`, `true-source-brand`, `broadcom-brand`) are now shortcuts to Harness Brand's one rebranding worker and are still found and run the same way. One that is not set up now says to run `rebrand setup` in the Harness Brand skill folder.

Unreleased: more ways on from a stop, and fewer wasted tries. A deck that stops on the desk now offers, beside **Try again**: **Review the slide text**, which goes back to what the deck says and draws nothing until you approve it, and **Finish without the deck**, which sets the deck aside with everything written for it kept, so the other materials can be marked ready and exported; **Bring the deck back** carries on from there. A stop now says what the checks actually refused instead of "It ended without handing anything back". A step refused twice in the same words is not tried a third time. When the brand cannot draw its own sample slide, the training stops at the look step, before any section is drawn. Ticking **Walk through each slide's design** no longer switches off the slide text approval on the desk.

Unreleased: a research run that has kept nothing moves to the installed Harness Research. A training or deck is tied to the helper version it started with, so one started before an update kept that version's limits (200 entries) even after a newer helper was installed. While research has registered nothing yet, the run now moves to the installed stable release and takes what it takes; a run with saved research stays with the helper that wrote it.

Unreleased: Change settings chooses the materials. Its Materials section now has the learner guide, reference brief, practice scenarios and Yoodli scenarios to tick, as the start form does. One with work in it stays, and practice scenarios stay as chosen once the blueprint is written. Unaccepted research starts again with the plan kept, because research is told which materials are wanted.

Unreleased: one research run reads up to 1,000 links, or 2,000 files and pasted texts, with Harness Research 1.2.0 (was 100 and 200). Sources are registered a hundred at a time, so a long list starts quickly. An older installed Harness Research still takes 200 entries and says so when research starts.

Unreleased: research reads many documents in groups. With more than fifty readable sources, the documents are divided into groups of at most fifty and one reader per group notes what each covers and which research areas it bears on; each area's investigator is then given the fifty that bear on it most, never more. Every document is read by some agent. The research screen shows how many have been read and which are open, and a retry reads only the groups that did not finish. Fifty sources or fewer are researched as before. A run is still held to what the installed Harness Research takes in (200 entries, a link counting as two), and now says so before it starts.

Unreleased: the Sources step counts what research will read. Its tab said **0 documents selected** however many links and files were added, because it counted only library documents. It now says, for example, **766 sources · 3 not read**, and follows the list as it grows. Each link's row is named by its page title and says how much text was read, and a file chosen while a long list of links is still being read waits its turn instead of being dropped.

Unreleased: links can be added from a file. Where a new training's sources are chosen, and in **What research reads**, **Add links from a file** takes a text, Markdown, CSV or saved web page file and adds every https link in it as a source, each once. The page says how many were added, which were already there and which could not be read. Links are not counted against the 40 files and pasted texts a request takes, so a file adds as many as it holds.

Unreleased: a training can start as practice only. The New training form begins with **What to make**: **A full training**, as before, or **Practice only, from my documents**. Practice only sets the outputs to the reference brief, practice scenarios and Yoodli layouts, with no learner guide and no slide deck, and has research read only the documents you add, with web search off. Each of those can still be changed in the steps that follow. It still makes one Quick scan and a plan for you to approve first.

Unreleased: a deck can change brand after it is made, without being made again. **Change brand**, under **Deck actions** beside **Try another look**, hands the deck as it is to a rebranding skill on this computer (such as `true-source-brand`, `tanzu-brand` or `broadcom-brand`) and gets back a new Google Slides copy in that brand: the same words, slide order, notes, charts and pictures. Nothing is drawn again and no assistant is asked, so it takes minutes. The deck and the training stay as they are; the copy's link is shown on the deck. A deck kept as a PowerPoint file is put in Google Slides first. The same sheet can still draw the whole deck again in another of the brand skill's brands, which keeps what the deck says and takes as long as the first drawing.

Unreleased: easier to move through a deck and to mark practice ready. A deck on the desk has **Back** and **Next** beside its slide list, with the slide's place in the deck. Where a training has several practice scenarios or Yoodli layouts, **Mark all ready** marks every one that waits, after one confirmation that names them; the other materials stay as they are.

Unreleased: a studio's own shared settings page shows its design again. Its script and styles were being refused after page scripts became cacheable.

Unreleased: a deck checks and fixes itself, and stops asking you about what it can settle. The slide text is written, then checked and corrected once by a second assistant against the plan, the guide and the sources, before you see it; you are shown only the corrected text. After the slides are drawn and reviewed, one pass of fixes runs without asking: slides with anything wrong in how they are drawn are drawn again, wording the review faulted is corrected where the correction can be made or looked up, and the review looks again at what it flagged. There is no second pass. What is left is kept as **Review notes** on the deck, to read; it does not need you and does not hold **Mark ready**. Only a question that is yours to decide (what you intend, a fact the sources do not hold, a choice between valid options) waits for you, as one numbered question. **Your move** also says when drafts can be marked ready while work continues, offers **Resume training** on a paused or stopped run, and approving the slide text or the outline no longer jumps to the top of the page. Trainings already under way keep the slide text they have; a deck already drawn gets no pass of fixes it did not have.

Unreleased: a deck no longer stops at "Presentation ID must be a Google Drive ID". A render that failed in the slides tool's shared preview files left a receipt, not a Drive file, as the deck's remembered preview; the deck's own named file is now made new when that is all there is.

Unreleased: a deck drawn from an approved design no longer stops at "The preview deck changed while it was being read". The render the review is made from is now taken again, up to three times, and kept in a Drive file of that deck's own, named after it, as the ordinary whole-deck preview already was. The earlier fix had missed this path.

Unreleased: what a deck says comes to you as text before any slide is drawn, again. **Approve the slide text before the deck is drawn** is ticked to start with on the form; untick it to have the deck drawn straight from its words. Trainings already started keep what they began with.

Unreleased: a deck's Google preview is steadier and easier to find. A preview Google changed while it was read back is taken again, up to three times, before the training stops for it. The whole deck's preview is kept in a Drive file of that deck's own, named after it, not in one of the slides tool's shared "Harness Slides preview" files; a section's working previews still use those.

Unreleased: a stop reads cleanly. The **Your move** card says what went wrong in one line and wraps long words; the full account stays in the stop under it, without the slides tool's command-line advice or a raw address.

Unreleased: a new training no longer stops when the independent check flags research. An assistant decides each flagged item: it keeps minor points, warns where the doubt is real, and leaves out only a very important claim that a source directly contradicts, with newer documents usually winning. Each choice and its reason is kept in the evidence as automatic, never as your decision. Tick **Decide flagged research myself** on the form to keep the choices; trainings already started keep them.

Unreleased: assistant work is never stopped for how long it takes, because ending it discards what it had done. **The longest a step may take** is gone from Settings, a time saved there is kept in the file and ignored, and a step runs until it finishes or you press **Stop**. Only the Quick scan keeps its 4.5 minutes, since it has an outline to fall back on. A training saved while stopped for time carries on with **Give it more time and try again**, now with no limit.

Unreleased: a deck is drawn straight from its words. The stop to approve slide text is now asked for: tick **Approve the slide text before the deck is drawn** on the form. Trainings already started keep the approval they began with.

Unreleased: Fable 5.2 is in the Claude Code model list, and **Fable, always the newest** now means it.

Unreleased: the assistant has 50% more time before a step is stopped. A step may take up to 22.5 minutes, not 15, the Quick scan 4.5 minutes, not 3, and the final brief of sectioned research 7.5 minutes, not 5. A limit you already saved in Settings, under Limits, keeps its value.

Unreleased: spending limits are removed. The project spending amount in Settings, the **Spending behavior** choice and the spending warning are gone, and work no longer stops or warns for what it costs. Time limits, tries and an account's own usage limit still apply, and the desk still shows what the assistant reported. Saved work that stopped at a spending limit carries on with **Carry on**.

Unreleased: the desk's status lines agree. A training that is still being written says its finished drafts are ready to read, on Home and on the desk, and asks for them only once it waits on you; the arc stays on Make while drafts are read and reaches Ship when every material is ready. The rail is as tall as its own parts, and the workflow, **About Ready and delivery** and the activity log sit under the material.

Unreleased: a training's desk is a workbench. Its materials are listed on the left, the material you are reading fills the middle, and one rail on the right holds the Brief, Plan, Make, Ship arc, **Your move**, and what the assistant is doing. Press **F** to read the material alone.

Unreleased: a training's stages are one drawn line, the progress track, with the stage waiting for you in amber; **Search and jump** (Cmd or Ctrl+K) and a Light, Dark or Auto appearance sit at the foot of the sidebar.

Unreleased: the desk says where a level stands in one line (ready to read, marked ready, awaiting your review) with **What is left** under it, and the progress line offers finished drafts instead of saying nothing is needed while they wait. A deck now needs Harness Slides 0.17.0 or newer.

## Unreleased — 4.14.0

Give your outline as a file or a link instead of pasting it. Under **What should it teach?** on the start form, **Upload an outline** takes your course outline, agenda or syllabus as a file (PDF, Word, Markdown, text or HTML), tables and all, and **Link to your outline** takes a Google Doc or a web page, read with your existing Google sign-in. It is followed as written: the training's parts are the outline's parts, and your other sources fill in the detail. With an outline given, typing what it should teach is optional. The outline is listed under Sources with the rest, where a Google Doc's tabs can be chosen, and removing it in either place removes it from both.

Your own outline is the plan, and your own documents are the facts. When one of the documents you add is your outline, agenda or run of show for the training, the quick scan now recognizes it and follows it: one section for each part that teaches, in your order and under your titles, with your welcome and wrap-up kept for the start and the end. The blueprint is then built from that document: each point and each row of its tables is taught, filled in from your other documents, with your timings. Research no longer treats what your documents say as a vendor's claims to audit. It reports them as the working facts, and where two of them disagree the newer and more specific one is taught. The automatic decision on flagged research keeps a finding whose one detail was questioned instead of leaving the whole of it out, and the check's warnings now reach the writers as corrections, never the learner. The blueprint, the learner guide, the brief and the deck say what is true in your organization's voice: no "planned ... would", no "the vendor says", no advice to confirm before promising, and no commentary on the evidence. A product brief's Unknowns is a short list of what to settle before promising it to a customer. A presented session is no longer told that a part serving one objective is too thin.

A training now teaches the brief you give it. Paste an abstract, an agenda or objectives into **What should it teach?** and they are followed as written: your objectives are kept in your words (the quick scan, the outline you approve and the blueprint no longer split or add to them), the order you describe becomes the modules, and a demonstration you name keeps its place and its minutes. The blueprint is written from the outline you approved as well as from the research.

What you state about your subject is taught as you stated it. A claim research found no source for is marked `[stated]` in the blueprint, taught at full strength in the guide and the deck, and listed in the review notes for you to confirm, with what the sources do say. Before, it was dropped and the training taught learners to verify it. A statement of yours that a source contradicts is still left out, and the notes say so first.

A training is a presented session unless you ask for a hands-on workshop. A session opens each part on why it matters, explains with an example or a demonstration and puts one question to the room; the running scenario, pair activities and activity slides appear only in a workshop. The guide and deck teach the subject, not the evidence: they say what is true and cite it, answer each objection directly, say plainly where the product does not fit, and write as your organization to its own people at their level. Research gaps stay in the notes to you.

The roadmap across the top of a desk is drawn as a route: tinted as far as the work has come, with numbered marks, a line under each phase saying what it is, and a line that moves while the assistant works. Page scripts and styles are compressed and reused instead of downloaded on every open.

Each finished draft can be marked ready as soon as it is written, while the materials built from it are still being made. Marking a whole level at once still waits until every material in the level has a draft.

Completed research sections expose saved read-only prose before final checking. Previews name their revision and assigned sources and remain ineligible for delivery. Queued concerns save privately across reloads without changing evidence or starting work; apply actual changes through the existing explicit refresh/impact flow. Timing separates the first readable section from the checked result.

## Unreleased — 4.13.1

Idle desks check a compact change signal before reading content again. Active work keeps its existing cadence; focus and reconnect catch up immediately. Incomplete metadata checks fall back to full reads, and connection failures back off.

## Unreleased — 4.13.0

Slide-text review shows one slide at a time with a compact picker and collapsed speaker notes. Corrections, feedback and selection save privately across reloads without starting work. Earlier corrections remain available when the outline changes; approval uses only the exact validated current text.

## Unreleased — 4.12.0

New work warns and continues at its project spending amount by default. Shared settings can choose Stop and ask; saved work has an explicit, stale-safe spending choice. Old tasks keep hard-stop behavior and Carry on. Warning mode supplies a $5 budget per job, keeps smaller Quick-scan budgets and time limits, records crossings once in Activity and shows them on the desk and home. Dollar enforcement and reporting depend on the assistant. Policy saves start no work or new research.

## Unreleased — 4.11.1

Saved work publishes compact metadata for Marketing Studio’s Needs you, In progress and Recent work overview. Direct resume opens the saved editing/decision context. Metadata browsing starts no studio or provider work.

## Unreleased — 4.11.0

New section workflows preview affected research before refresh. Added sources can target selected sections; changed or removed inputs require wider invalidation. Retained investigator packets and drafts are revalidated, and assembled research still needs a fresh independent check. Wording, notes-only edits and existing section updates keep their direct routes.

## Unreleased — 4.10.0

New outline-first work keeps section contributions across retries, combines at most three at once, and gives only a timed-out contribution more time. A short final author reads the contributions; the supported independent whole-report check still gates use. Existing saved flows retain their schemas and helper versions.

## Unreleased — 4.9.1

- Share strict provisional-outline validation and bounded source excerpts with Presentation
  Studio; the saved Training Studio workflow and approval contract remain unchanged.

## Unreleased — 4.9.0

- Outline-first records use schema 7 so older runtimes refuse to drive them. Existing
  schema-6 topics-review records keep their saved flow.
- New runner trainings start with one bounded Quick-profile scan and an editable outline.
  Save edits without assistant work; only Approve outline & research starts detailed
  research. Removing a section removes its research scope. Form questions stay visible.
- The scan uses bounded excerpts, no external searches, at most 180 seconds and $0.25
  within existing training limits. A stop or time cap keeps a usable incomplete outline;
  no automatic second author or escalation runs.
- Approved sections use the pinned Harness Research collection protocol, at most three
  areas at a time, followed by the existing combining and whole-dossier independent
  check. Materials receive the approved scope and checked evidence. Supplied-only stays
  supplied-only; the provisional scan is never research evidence.
- Existing work keeps its saved flow. Eligible stopped work before a report/teaching plan
  can explicitly adopt after a preview; inputs, spending and private unfinished research
  history are preserved. Adoption starts no job and waits for Resume training.
- Presentation Studio's corresponding outline-first flow remains a separate cohort.
  Independent section-review receipts and later incremental research reuse remain later
  companion work; no Harness Research protocol was changed here.
