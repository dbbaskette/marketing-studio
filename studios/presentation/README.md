# Presentation Studio

Presentation Studio makes slide decks in your brand. You give it an idea, a document or a deck you already have, and it builds the deck with you.

A deck you start on the page starts on the desk, in three steps: the kind of deck, its sources and settings, and what you have. It then runs with no stops, except a pick of the look when you chose to pick it, and opens on the desk: a card for each slide, under its section. A note on a card redraws only that slide's section, and the other slides stay exactly as they are; a note for the whole deck redraws every section, with **Stop**. Every redraw says first what it last took on this computer, or that there is no record yet ("expect minutes, not seconds"). You change a slide's words and its speaker notes on its card, and **Deliver** is always yours. [The desk](#the-desk) says more.

A deck started in a conversation, and every deck started before the desk, is a gated deck: it keeps the flow in [What you do at each step](#what-you-do-at-each-step), with your shared review level. Balanced brings research, the outline and the brand's looks together for one review, where you pick the look, then shows the finished deck; a deck redesigned with its content kept, which has no outline stop, stops for its look instead. Automatic draft stops at the finished deck and uses the brand's default look; Step by step reviews every stage. Existing runs keep their saved flow, and once delivered they can be opened on the desk. Review levels govern only these saved decks, and Training Studio: a desk deck has none.

The work is done by an AI assistant you already have, Claude Code or Codex. Presentation Studio guides it, checks what it makes, and keeps track of what you have approved. The runner works within your selected permissions and limits. Automatic continuation is recorded separately from your own approvals; publishing remains a separate action.

It is the third studio beside [Training Studio](https://github.com/dbbaskette/marketing-studio/tree/main/studios/training) and [Blog Studio](https://github.com/dbbaskette/marketing-studio/tree/main/studios/blog), and made for colleagues who are technical or not.

## Three ways in

| You have | Choose | What happens |
| --- | --- | --- |
| An idea | **Start from scratch** | You give it a title, audience and goal, with an optional brief of up to 4000 characters for points, examples or a rough order. The brief reaches the research plan and outline. Research is optional and off unless you turn it on. |
| A document | **Start from a document** | A Markdown or text file, a Word file, a PDF, a Google Doc or pasted text. The studio says whether it thinks the document lays out the slides or is material to turn into slides. You can correct it. |
| A deck | **Redesign an existing deck** | A `.pptx` file or a Google Slides link. You choose how much may change (below). Your original is never changed; you always get a new copy. |

Redesigns come in five levels:

- **Brand only**: same slides, your brand's look.
- **Polish**: brand plus tidier layouts and spacing. The words stay.

At Brand only and Polish a slide with no words of its own, such as a picture alone, gains none when it shows one picture (a PNG or JPEG) that fits the picture slot of one of your brand template's layouts that shows no title. Otherwise the slide is drawn under the short title you approved in the outline, with its picture where it can be carried, so nothing on it is lost, and the build says so beside that slide.
- **Redesign, keep content**: rebuilt with your brand's layouts, icons and diagrams. Same message on each slide.
- **Full rework**: may tighten, split, merge or reorder the content, then redesign it.
- **Selected changes**: you say which slides and what to fix.

## The desk

This is how a deck you start on the page is made, from an idea, a document or a deck you have.

**The start.** **New deck** opens one sheet in three numbered steps, with **Start** at its end.

1. **Kind of deck**: an idea, a document or an existing deck. An existing deck shows its five levels on the same step, and Selected changes asks which slides, and what to fix.
2. **Sources and settings**: research, on or off, with where it may look and up to eight questions (an existing deck has no research); the minutes, the audience, a talk or a handout, the brand and variant, and the output. **Look** is "Pick it when the samples are drawn" (the default) or "Use the brand's default look", for every kind of deck whose looks are drawn. The assistant and its model are under **Options**. There is no review level here.
3. **What you have**: the title and the goal, and the brief, the document or the deck. A document can be marked "It lays out the slides" or "It is material to build from"; left unmarked, it is read first to tell which.

**While it is made.** Nothing is needed from you: the page says so, with about how many minutes are left from what each step took on this computer, or that this computer has no record yet. The slides take shape as they are drawn, and each preview has a note box, "How should this slide change?". The one pause is the look, when you chose to pick it: the samples lead the screen, and your pick carries the deck on. A question from the assistant, a step that failed and the spend limit come first, above everything else.

**A card for each slide.** On the desk the slides sit on cards under their sections, each with its picture, its words, its speaker notes and what the brand check and the review found on it. The toolbar has **Deliver**, **Download**, **Finishing** and **More**.

- **A slide note.** "How should this slide change?", with **Redraw slide N**, redraws only that slide's section; every other slide stays exactly as it is drawn. The line under it says what that last took here, or "This computer has no record yet of what it costs. Expect minutes, not seconds." A cover, section or closing slide has no note box: change its words instead.
- **The whole-deck note.** "How should the whole deck change?", with **Redraw every section**, redraws the sections three at a time, and the line above the desk counts them. **Stop** keeps what is redrawn so far and puts the deck together from it; the slides not redrawn say so, with **Redraw slide N**.
- **Words.** A slide's title, subtitle, points, caveat and source are boxes on its card, saved a second after you stop typing. Selecting words offers Rephrase, Shorten, Expand, Fix and Ask…, which a small assistant job does. Words that still fit the slide as it is drawn are put into the drawing with no redraw; words that do not fit are not saved, and the card offers **Redraw with these words**, priced, or **Discard**.
- **Speaker notes** are their own box on the card. Saving them redraws nothing.
- **History.** Before a slide's words or notes change, they are kept as a version. **History** on the card lists the versions, compares one with the words now and brings it back with **Restore**. The words are shared with your team; the slide's drawing and picture at each version stay on this computer, so another computer restores the words alone.

**The Outline tab** is the outline editor: reorder, add and remove slides, and edit their words. Before **Save** it says how many sections change and are redrawn; the rest stay as drawn. A deck from a document says how it was read, with **Read it the other way**, and **Change the look** draws the looks again for another pick. Each says its price first.

**Add a source** takes a file or pasted text. The words jobs, the speaker notes and the outline, when it is written again, read your sources; adding one runs no research. With research on, the Research panel shows the findings and the gaps, with **Research again** and **Leave out**, each priced first.

**Finishing** proposes, and nothing changes until you press **Apply**:

- **Brand check**: the last render's check, slide by slide, what blocks delivery first. **Check again** runs it on the deck as it is now, in seconds. Apply redraws a slide's section with the check's words as its note.
- **Review the deck**: a reviewer looks at every slide, and what it finds comes back on each slide as a proposal, with **Apply** (that slide redrawn, priced) or **Skip**. Nothing is sent back to be drawn again by itself.
- **Speaker notes**: notes proposed for every slide, each beside the notes it has. Applying them redraws nothing.
- **Rehearse**: how long your speaker notes take to say, at about 150 words a minute, against your minutes, with the slides that run long.

**Deliver** sends the deck on screen, once nothing is being redrawn. When the brand check found problems that block delivery, a sheet first lists each one with its slide, with **Deliver anyway**. The sheet says whether the deck was reviewed, and the delivery records it; a desk deck's title is never labelled a first draft. A change to a delivered deck makes its next revision: "Delivered as revision 2. A change here makes revision 3, delivered when you press Deliver." The revision delivered stays as it was.

**An existing deck** comes to the desk at its five levels:

- At Brand only, Polish, Redesign, keep content and Selected changes, each card shows the slide's **Before**, as it was in your deck, beside its picture now.
- **Brand only and Polish keep your words** exactly, so a word edit is refused, with a sentence that says so. Speaker notes can still be changed, and a note on a slide still changes how it is drawn.
- **Selected changes** changes your deck's text through patches to a copy. Your words are changed in their boxes on the card, and a note on a slide plans its changes again. Your deck itself is never changed, its speaker notes stay as they are, and there is no whole-deck note or Finishing.

**Open on the desk.** A gated deck that is delivered offers **Open on the desk** on its screen. It opens from this computer's drawing of the deck, still delivered, and its first change there makes the next revision. From then on it is a desk deck, with no review level. A computer without that drawing says so: draw it there first, or open it on the computer that made it.

**With a team.** A teammate's computer has a desk deck's words, not its drawing: the desk says "There is no drawing of this deck on this computer." and offers **Draw it here**, priced. It is never redrawn there unasked.

## What you do at each step

This section describes gated decks: a deck started in a conversation, or before the desk. A desk deck passes these stops on its own, with a receipt that says the desk continued it. Which of these a deck has depends on how you started. Where it stops depends on its review level, chosen for the deck under **Where this deck stops** on the form: at Step by step the page stops at each of these and waits for you; at Balanced and Automatic draft it stops only where the list says, and carries on by itself in between, recording that it did.

1. **Check what you brought** (documents and existing decks). You see the verdict, or the original slides as pictures. Step by step stops here. Under Balanced the way a document was read is shown again at the direction review, where it can be put right.
2. **Research plan and research** (only if enabled). Choose where research may look, in any combination: **your documents** (a deck from a document, on by default), **your sites** (off until you tick them; the list of sites in Shared settings, which you can narrow or add to for one deck without changing the list) and **the public web** (on by default for a deck from an idea). Your sites are searched with your assistant's own web search tool. With your sites on and the public web off, research saves pages only from under your sites, and the research review says how many pages it could not save from elsewhere. Add up to eight optional questions on the form. Supplied-only synthesis writes its plan without a planning job. The research review shows the authored brief, independent check, gaps and source limitations, with findings under your questions. The report and evidence are a click away. Asking for changes reruns the whole investigation and is priced before sending. Step by step stops at the plan and at the research. Under Balanced the research is shown in the direction review, where leaving findings out redraws only the outline and looks. Research needs Harness Research 1.0 or newer: on an older one, **Start the deck** refuses a deck with research on, with a sentence saying to update Harness Research.
3. **Outline.** A title and what each slide must make clear, with its points and notes a click away. You can reorder, add and remove slides, and ask for changes to any one of them. Step by step stops here. Balanced stops here for the direction review: the research, the outline and the brand's looks together, where you pick the look. Automatic draft does not stop.
4. **Look.** The brand draws one slide of your outline in each of its looks, side by side. Pick the one every slide is drawn in, and say why if you like; or choose another brand or variant and see its looks. If the looks cannot be rendered on this computer, try again, or carry on knowingly in the brand's default look: the deck is then marked as an unreviewed draft of its look. Step by step stops here. Balanced picks the look in the direction review, from the samples shown; edit the outline there and its looks are drawn again, for you to choose from before the build. A deck redesigned with its content kept has no outline, so under Balanced it stops here for its look. Automatic draft does not stop, and uses the brand's default look, saying so. A brand skill older than the version decks need stops a new deck before its brand is used, with a sentence saying to update it in Settings.
5. **Build.** The whole deck in a slide viewer, plus a contact sheet and notes from the brand check. Redesigns show before and after. Each slide has its own **Ask for changes**. Every level stops here. While the deck is being built, **Slides taking shape** shows each slide's preview as it is drawn, marked **Unreviewed**: looking at them approves nothing, and the whole-deck review and your decision still follow. **Ask for changes to this slide** there sends a note to the part that draws it while the others keep working; a note that comes after that part is drawn is kept as the slide's mark at the deck review. Previews already drawn stay on this computer after an interrupted render or a reconnect, and a new attempt replaces the earlier one's.
6. **Deliver.** Approving the deck delivers it: a Google Slides deck by default, or a PowerPoint file.

**See the first draft before the deck is checked**, under Options on a gated deck's form, builds and renders the deck without its check and repairs. It stops as **First draft, not checked**, where **Check the deck** runs them and **Use this first draft** takes it as it is. A deck delivered that way says **Delivered: first draft, not checked**.

Your brand comes from your brand skill: the brands and variants it lists are the ones offered when you start a deck, and the first it lists is the default until you choose another. Presentation Studio names no brand of its own.

## Before you start

You need:

- **A Mac.**
- **Claude Code or Codex.** The guided installer offers missing CLIs; sign in afterward.
- **Python, Node.js and Git.** The guided installer checks versions and offers missing prerequisites.
- **The fonts your brand skill names**, installed on this computer.
- **A way to see slides**: LibreOffice and Poppler on this computer, or Google Drive previews if you sign in to Google.
- **Google sign-in** (gcloud), only if you want Google Slides as the output or a Google Doc as the input. Without it you get a PowerPoint file.
- **Two companion skills**: [harness-slides](https://github.com/dbbaskette/harness-slides-skill) builds the decks and [harness-research](https://github.com/dbbaskette/harness-research-skill) does the research. The installer brings both at the versions it was tested with.
- **Your brand skill**: a skill that holds your organisation's brands, its slide template and its icons. It is your own, so the installer does not bring it. Install it yourself, or name its repository in Settings and install and upgrade it from the page. Without one, a deck is made up to the point it needs your brand, and waits there.

The page checks this computer the first time you open it and says in one sentence what is missing.

## Install

This source folder has `package.sh` to build an independent Presentation Studio
bundle and `install.sh` to install Presentation Studio. The Marketing Studio root
has the same filenames for the complete suite. See [package and install the studios](../../docs/packaging.md).

**[Download the Presentation Studio installer](https://github.com/dbbaskette/marketing-studio/releases/latest/download/presentation-studio-installer.zip)**
and unzip it. Open Terminal in `presentation-studio-setup` and run `bash install.sh`
on macOS or Linux. No `.command` launcher is needed. The subset
installs Presentation Studio with its own independent launcher.

Or install from the consolidated source:

```sh
git clone https://github.com/dbbaskette/marketing-studio.git
cd marketing-studio
bash install.sh --studios presentation
```

Use `--target codex` or `--target claude` for one assistant. Setup offers missing
prerequisites, assistant CLIs, and pinned research/slide tools. Compatible existing
tools and workspaces are reused; sign-in and your brand remain your choices.
Close running studios before installing an update.

See the [guided installation reference](../../docs/installation.md) for offline
setup, updates, rollback, and removing the Marketing Studio launcher. Native
studio commands and your content remain independent.

## Your first deck

**1. Open Presentation Studio.** Double-click "Open Presentation Studio" in the Applications folder inside your home folder, or run:

```bash
sh ~/.local/share/presentation-studio/studio
```

A terminal window opens and the page opens in your browser. It works on this computer only. Leave the window open while you work.

**2. Set it up, once.** Say where decks are kept: a folder on this computer to try things out, or your team's shared repository. Then choose your assistant, your name, the brand and where decks are delivered. If you also use Training Studio or Blog Studio, the answers they share, such as the team repository and the assistant, are kept in one place for all of them, so a change in one studio is a change in all three (see [shared settings](#shared-settings)).

**3. Press "New deck"** and go through its three steps: the kind of deck, its sources and settings, and what you have. **Start** begins it at once.

**4. Let it run.** Nothing is needed from you, except the look when you chose to pick it. You can close the page while it works and come back later.

**5. Change it on the desk, and deliver.** Note a slide, change its words or its speaker notes, look it over with Finishing, then press **Deliver**. The page shows the Google Slides link or the PowerPoint file. A change after that is delivered as the next numbered revision.

A gated deck stops instead at each stop its review level keeps, and the page shows what needs you and what approving does. Once it is delivered, asking for changes on its screen draws again the sections that hold the slides you name (every section when you name none), reviews them and delivers a new numbered revision; or **Open on the desk** takes it to the desk.

### In a conversation instead

If you are comfortable in a terminal, open your assistant and ask for `/presentation-studio` instead of using the page. A deck started there is a gated deck: it follows the steps above and waits for you at each stop.

## Working with a team

Keep your decks in your team's shared repository. They go in a `presentations/` folder, beside Training Studio's `trainings/` and Blog Studio's `blogs/`.

- One computer runs a deck at a time. Teammates' decks are read-only, and you can **take over** one or **hand over** your own.
- Every decision you make is saved as a commit.
- Google Slides links are saved with the deck. A PowerPoint delivery is shared beside the deck as `deck.pptx`, so a teammate can download it too; one delivered before that stays on the computer that made it, and the page says so.
- Uploaded files and slide pictures stay on your computer. Teammates see a small contact sheet.
- The computer that delivered a deck can ask for changes to it directly; a teammate takes it first.

[The runner](docs/runner.md) has the details, including what happens when two computers disagree.

## Shared settings

`~/.config/studios-config.json` is the one place the choices common to every studio are kept: your team repository and branch, when to share, your name, your assistant with its model and level, the brand skill's repository and release, the brand and its variant, and the output. Presentation Studio keeps no copy of its own. It reads them from that file each time, and saving one of them in set-up or Settings writes it there, so Training Studio and Blog Studio see the change too. Limits, how slide previews are made and the other choices only Presentation Studio uses stay in its own settings.

If the file cannot be read, Presentation Studio works on its built-in defaults, says so in one sentence on set-up and Status, and saves none of the shared choices until the file is fixed. It never writes over that file. [The shared studios convention](docs/shared-studios.md) describes the file and its rules, identically for every studio, and [the runner](docs/runner.md#shared-values) says what each value does here.

## If something goes wrong

| What you see | What it means |
| --- | --- |
| The page says it needs LibreOffice or Poppler | Slides cannot be drawn on this computer. Install them, or sign in to Google and use Drive previews |
| You get a PowerPoint file, not Google Slides | You are not signed in to Google. Status → Check this computer says how to sign in; then press **Send to Google Slides** on the deck's screen: the same deck goes to Google Slides as the next revision |
| A step failed | The page says why in one sentence. Choose Try again, or Carry on if offered |
| A step ran out of time | The page says how long a step may take. Choose **Give it more time and try again**, or raise the limit in Settings, under Limits |
| A deck spent what it may | It stops before the next step, or when a step uses up what is left. Choose Resume to let it spend as much again, or raise the limit in Settings, under Limits |
| The assistant could not be used | It is not installed, not signed in or out of reach. Use **Check this computer** on the Status screen |
| The assistant's account reached a usage or rate limit | Wait until it resets, then choose Try again. Check this computer cannot show such a limit |
| The research check could not read a document | That is a studio problem, not a research problem. Try again works once the document can be read |
| Your team repository cannot be reached | Your work is kept and marked "not shared yet". It goes up with the next share |
| A deck cannot be read | The page gives the reason when you add it. Try saving it as `.pptx` again |
| The page does not open | Open the link exactly as the terminal printed it, and keep that window open. The part after `#` is a key |

## Learn more

- [The runner](docs/runner.md): how the page and runner work, and working as a team.
- [Development](docs/development.md): the repository, running the tests, and how to change Presentation Studio.
- [Acceptance](docs/acceptance.md): what has been tried by hand.
- [Design](docs/superpowers/specs/2026-10-14-presentation-studio-design.md): the first design, kept as history; [the runner](docs/runner.md) says how it works now.

## Licence

[MIT](LICENSE).
