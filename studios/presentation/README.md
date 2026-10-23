# Presentation Studio

Presentation Studio makes slide decks in your brand. You give it an idea, a document or a deck you already have, and it builds the deck with you one step at a time. New browser runs use your shared review level: Balanced brings research, the outline and the brand's looks together for one review, where you pick the look, then shows the finished deck. Automatic draft stops at the finished deck and uses the brand's default look; Step by step reviews every stage. Existing runs keep their saved flow.

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

## What you do at each step

The page stops at each of these and waits for you. Which ones apply depends on how you started.

1. **Check what you brought** (documents and existing decks). You see the verdict, or the original slides as pictures.
2. **Research plan and research** (only if enabled). A document defaults to your documents only; allow the public web explicitly if needed. Add up to eight optional questions on the form. Supplied-only synthesis writes its plan without a planning job. The research review shows the authored brief, independent check, gaps and source limitations, with findings under your questions. The report and evidence are a click away. Asking for changes reruns the whole investigation and is priced before sending. Under Balanced, leaving findings out redraws only the outline and looks.
3. **Outline.** A title and what each slide must make clear, with its points and notes a click away. You can reorder, add and remove slides, and ask for changes to any one of them.
4. **Look.** The brand draws one slide of your outline in each of its looks, side by side. Pick the one every slide is drawn in, and say why if you like; or choose another brand or variant and see its looks. If the looks cannot be rendered on this computer, try again, or carry on knowingly in the brand's default look: the deck is then marked as an unreviewed draft of its look. A brand skill too old to offer looks shows your cover in the brand instead.
5. **Build.** The whole deck in a slide viewer, plus a contact sheet and notes from the brand check. Redesigns show before and after. Each slide has its own **Ask for changes**.
6. **Deliver.** A Google Slides deck by default, or a PowerPoint file.

Rehearsal is not part of a deck yet, so the page does not show it.

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

**3. Press "New deck"** and choose how you are starting. Fill in the short form. It begins at once.

**4. Decide at each stop.** The page shows what needs you, and what approving does. Approve takes one click. Or ask for changes in your own words. You can close the page while it works and come back later.

**5. Collect your deck.** When it is done, the page shows the Google Slides link or the PowerPoint file. Ask for changes on a finished deck and the sections that draw the slides you name are drawn again (every section when you name none), reviewed, and delivered as a new numbered revision.

### In a conversation instead

If you are comfortable in a terminal, open your assistant and ask for `/presentation-studio` instead of using the page. It follows the same steps and waits for you at the same stops.

## Working with a team

Keep your decks in your team's shared repository. They go in a `presentations/` folder, beside Training Studio's `trainings/` and Blog Studio's `blogs/`.

- One computer runs a deck at a time. Teammates' decks are read-only, and you can **take over** one or **hand over** your own.
- Every decision you make is saved as a commit.
- Google Slides links are saved with the deck.
- Uploaded files and slide pictures stay on your computer. Teammates see a small contact sheet.

[The runner](docs/runner.md) has the details, including what happens when two computers disagree.

## Shared settings

`~/.config/studios-config.json` is the one place the choices common to every studio are kept: your team repository and branch, when to share, your name, your assistant with its model and level, the brand skill's repository and release, the brand and its variant, and the output. Presentation Studio keeps no copy of its own. It reads them from that file each time, and saving one of them in set-up or Settings writes it there, so Training Studio and Blog Studio see the change too. Limits, how slide previews are made and the other choices only Presentation Studio uses stay in its own settings.

If the file cannot be read, Presentation Studio works on its built-in defaults, says so in one sentence on set-up and Status, and saves none of the shared choices until the file is fixed. It never writes over that file. [The shared studios convention](docs/shared-studios.md) describes the file and its rules, identically for every studio, and [the runner](docs/runner.md#shared-values) says what each value does here.

## If something goes wrong

| What you see | What it means |
| --- | --- |
| The page says it needs LibreOffice or Poppler | Slides cannot be drawn on this computer. Install them, or sign in to Google and use Drive previews |
| You get a PowerPoint file, not Google Slides | You are not signed in to Google. Sign in with gcloud, then press **Deliver to Google Slides** on the deck's screen: the same deck goes to Google Slides as the next revision |
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
- [Design](docs/superpowers/specs/2026-10-14-presentation-studio-design.md): the full specification.

## Licence

[MIT](LICENSE).

### See slides while the deck is being built

The deck page shows **Slides taking shape** as preview images become available.
These pictures are marked **Unreviewed**. Inspecting them does not approve the deck;
the whole-deck review and your final decision still apply. Available images remain
on this computer after an interrupted render or reconnect. A new attempt replaces
its earlier preview, and an older attempt cannot overwrite that one.

Each section shows once its preview is finished, before the final review. Updating or
installing a companion remains an explicit action. Comments during construction are
tracked separately in
[the live-preview issue](https://github.com/dbbaskette/marketing-studio/issues/15).

The Balanced direction review requires a look from the samples shown. Editing the outline redraws those samples and asks you to choose again before the build. Delivered team decks stay their maker's to request changes; teammates still take them explicitly. A PowerPoint delivery can later be sent to Google Slides as a new revision from the page, without rebuilding.
