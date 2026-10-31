# Training Studio

Training Studio turns a topic into training material. You give it a subject, it researches it, and it builds the material with you one stage at a time. New trainings open on [the desk](docs/the-desk.md), where you can read and change materials as they are made.

Training Studio researches and prepares a short **Here’s what this training will cover**
review. Check the topics, depth and examples, then choose **Ask for changes** or
**Build the training**. Build creates the selected guides, slides and practice
materials automatically. There is no sample lesson to approve. Older saved runs
keep their original workflow. For a new deck, review and approve its slide text before design begins.

The writing is done by an AI assistant you already have, Claude Code or Codex. Training Studio guides it, checks what it makes, and keeps track of what you have approved.

## What you get

Research and a teaching blueprint connect the materials. Choose what you need:

- **A research report** with sources, so every claim can be traced.
- **A blueprint**: the learning objectives and outline.
- **A learner guide**: a document people read.
- **A brief**: a short reference about the subject. It is a product brief for one technology, or a competitive brief when you are comparing two.
- **A slide deck** that works both presented and handed out.
- **Practice scenarios**: a role-play situation you can write or edit yourself. If you use [Yoodli](https://yoodli.ai), it can also prepare a version ready to build there.

You can ask for one or more **levels**, from 101 (introduction) to 401 (expert). Each level gets its own set of material.

## Two ways to work

You can make a training in either of two ways. Both use the configured workspace and let you work as materials arrive.

| | On the page | In a conversation |
| --- | --- | --- |
| How you start | Open Training Studio and fill in a short form | Ask your assistant for focused work in the configured workspace |
| Who does the work | The runner starts an assistant for each step by itself | Your assistant, in the conversation |
| Where you approve | On a page in your browser | Only you can approve; checked submissions do not approve |
| Working with a team | Built in: your team shares one workspace | In the workspace; older conversation work can use the [team hub](docs/team-hub.md) |
| Best for | Getting a training made while you get on with other things | Steering each step closely |

Start on the desk for a guided workflow, or use a conversation when you want to steer each stage closely.

## Before you start

You need:

- **Claude Code or Codex.** The guided installer offers missing CLIs; sign in afterward.
- **Python, Node.js and Git.** The guided installer checks versions and offers missing prerequisites. Git also keeps your trainings.
- **Two companion skills**: [harness-research](https://github.com/dbbaskette/harness-research-skill), which does the research, and [harness-slides](https://github.com/dbbaskette/harness-slides-skill), which builds the deck. The installer offers to bring both. Without harness-slides you still get everything except the deck.

A slide deck made on the page also needs your organisation's brand skill and a way to turn slides into pictures. The page tells you what is missing. Once you name your brand skill's repository in Settings, the page can install and upgrade the brand skill for you. See [the runner](docs/runner.md#what-you-need).

## Install

This source folder has `package.sh` to build an independent Training Studio bundle
and `install.sh` to install Training Studio. The Marketing Studio root has the same
filenames for the complete suite. See [package and install the studios](../../docs/packaging.md).

**[Download the Training Studio installer](https://github.com/dbbaskette/marketing-studio/releases/latest/download/training-studio-installer.zip)**
and unzip it. Open Terminal in `training-studio-setup` and run `bash install.sh`
on macOS or Linux. No `.command` launcher is needed. The subset
installs Training Studio with its own independent launcher.

Or install from the consolidated source:

```sh
git clone https://github.com/dbbaskette/marketing-studio.git
cd marketing-studio
bash install.sh --studios training
```

Use `--target codex` or `--target claude` for one assistant. Setup offers missing
prerequisites, assistant CLIs, and pinned research/slide tools. Compatible existing
tools and workspaces are reused; sign-in and your brand remain your choices.
Close running studios before installing an update.

See the [guided installation reference](../../docs/installation.md) for offline
setup, updates, rollback, and removing the Marketing Studio launcher. Native
studio commands and your content remain independent.

## Your first training, on the desk

**1. Open Training Studio.** On a Mac, double-click "Open Training Studio" in the Applications folder inside your home folder. On any system, run the line the installer printed:

```bash
sh ~/.local/share/training-studio/studio
```

A terminal window opens and the page opens in your browser. Leave the window open while you work.

**2. Set it up, once.** Say where trainings are kept: a folder on this computer to try things out, or a git repository your team shares. The page checks each answer as you give it. If you use Presentation Studio or Blog Studio too, the answers they share, such as the team repository and the agent, are kept in one place for all of them, so a change in one studio is a change in all three (see [the shared studios config](docs/runner.md#shared-studios-config)).

**3. Press "New training".** Describe what learners should be able to do and what they know already. Choose the materials: a guide, reference brief, deck, practice, or a combination. Set the learner's time and choose where the research looks: your documents, your sites (a list of web addresses you keep in Shared settings) and/or the public web. The final summary shows your choices before you start. Depth, extra copies and assistant settings are optional details.

**4. Check the topics, then build.** Review what will be taught across the selected levels. Ask for changes in plain language, or choose **Build the training**. There is no separate sample lesson. If you selected a deck, review its slide text before design begins. Materials then appear on the desk as they are made. Read them, make changes, and mark each one ready when you are satisfied. The desk shows work that needs your attention. You can close the page while it works and come back later. See [the desk](docs/the-desk.md).

See [the runner](docs/runner.md) for every step, the slide deck, working as a team, and what it guarantees.

## Your first training, in a conversation

**1. Set up the workspace.** Complete Training Studio setup first. New conversation work uses that configured workspace; it does not start in an arbitrary topic folder.

**2. Ask for the work you want.** Start your assistant and say, for example:

> Use training-studio to make a teaching plan for a 101 training on Valkey for teams running Redis.

Describe the audience, purpose, levels, and materials you need. Your assistant chooses a finite scope for that request: an outline-only request does not also authorize research or drawings. Tell it about any local documents you want used; original uploads and source scope are pinned. Google and Word copies and Yoodli are off unless you explicitly request them.

**3. Work through the checked desk.** Your assistant creates the work with `studio desk create`, reads its context with `studio desk context`, and submits material with `studio desk submit`. The [conversation instructions](skills/training-studio/references/conversation.md) explain the inputs and checks. Creation starts no worker and does not check assistant readiness; conversation work needs no nested assistant. Answer questions and make decisions yourself. A checked submission is not approval or Ready: only you can approve, and work remains Draft when requirements are unmet.

**4. Come back or hand over deliberately.** Ask your assistant to continue the work in the workspace. A page visit or restart does not transfer it to the runner. If you want the runner to take over, explicitly request a handoff; it checks the remaining plan, scope and readiness first. See [conversation handoff](docs/runner.md#conversation-handoff-and-saved-work).

Older saved conversation trainings can still follow their saved seven-stop review and import path; that is compatibility for existing work, not a new start. See [saved-work compatibility](../../docs/saved-work-compatibility.md).

## Levels

Ask for the levels you want when you start, for example "101 and 301".

| Level | Covers |
| --- | --- |
| 101 | What it is and why it matters |
| 201 | How it works and common tasks |
| 301 | Architecture, tuning and troubleshooting |
| 401 | Internals and design at scale |

Research is done once and shared. Each level then gets its own folder, such as `101/` and `301/`, with its own blueprint, guide, brief, deck and scenarios. You can add a level later.

## Writing your own scenario

A scenario is a short file that describes a practice conversation: the situation, who the learner is, who the AI plays, how it opens, and what success looks like. Write it in plain language. This is a complete one:

```markdown
# Scenario: IT executive weighing Redis alternatives

## Situation
You are an IT executive with Redis applications in production. You want lower costs without risking reliability.

## Learner role
You are advising the executive on how to evaluate Valkey.

## AI role
Play the executive: cost-conscious, open to alternatives, sceptical of claims that ignore migration effort.

## Opening
"We have Redis in production. Where would you start?"

## Success criteria
- Asks about the current deployment before recommending anything.
- Separates what is known from what is assumed.
- Proposes a measured evaluation and a next step.
```

Save it as `scenario.md` in your training folder, or put several under `scenarios/`. Training Studio uses your file as written and never overwrites it. If you do not write one, it drafts one for you to edit. See [scenarios and Yoodli](docs/scenarios-and-yoodli.md) for the full format.

## Using the scenarios in Yoodli

This part is optional. A scenario file already works with any AI that can play a role. If you use Yoodli, say "also make Yoodli scenarios" when you start, or "add Yoodli" at any time. On the page, choose "Make scenarios for Yoodli" in "New training".

For each scenario, Training Studio then writes a file under `yoodli/` laid out in the same order as Yoodli's roleplay builder, so you can copy each part into its field. It also tells you which file to upload as the AI's reference material. You build the roleplay in Yoodli yourself; Training Studio does not upload anything. See [scenarios and Yoodli](docs/scenarios-and-yoodli.md).

## The Document Library

Training Studio shares the Document Library that every studio keeps on this
computer. It holds uploads, finished blogs, delivered decks and finished training
material.

- **Add from library.** The documents card, and the desk's **Research & sources**,
  have **Add from library**. Each chosen revision is copied into the training as one
  of its documents, so the training keeps it if the library changes. A newer revision
  is shown, and **Use revision N** takes it. Adding one starts no research. While the
  training waits for its documents, it is read with the rest. After the research it
  waits, not read yet, until you choose **Update the research**, which says first what
  it changes. A training whose research does not read documents takes none: adding
  from the library never widens where research looks. Both are refused while a step
  is being worked on.
- **Keep in library.** When you add a document, **Keep in library** also keeps a copy
  in the library for other projects, and **Only this project** keeps it in the
  training alone. Neither changes who it is shared with.
- **Finished material.** Marking a learner guide or a brief ready on the desk keeps it
  in the library as Markdown, as learners read it, without its coverage notes. Marking
  it ready again adds a revision only when its words changed. If that save fails, its
  card says so and offers **Keep in library again**. Decks are not kept yet, because
  Training Studio cannot export a PDF of one.

Nothing in the library is shared with your team or committed to your workspace. See
[the Document Library](../../docs/shared-setup.md#the-document-library).

## If something goes wrong

| What you see | What it means |
| --- | --- |
| It stops at research and names harness-research | That skill is not installed. In the Training Studio folder you downloaded, run `sh installer/install.sh --companions install` |
| The deck is "unavailable" | harness-slides is not installed. Everything else still works. The same command installs it |
| The page says the deck needs something | This computer is missing part of what a deck needs. The Status screen says what, and how to get it |
| A Word copy is "unavailable" | You asked for Word copies and no converter was found. Installing [pandoc](https://pandoc.org) fixes it |
| Something is out of date | A file it was built from has changed. Ask to rebuild it, or say it is fine as it is |
| It refuses to start in a folder | The folder already holds files with the names it uses, or it is the Training Studio folder you downloaded. Use a new folder |
| The page does not work | Open the link exactly as the terminal printed it, and keep that window open. The part after `#` is a key |

## Status

Training Studio is early, so expect rough edges and please [report them](https://github.com/dbbaskette/marketing-studio/issues).

The programs that track your files, and the runner behind the page, have automated tests. A whole training has been made on the page, from the form to its finished files, and another as far as its slide deck. A full run through every stage in a conversation, a roleplay built in Yoodli, and a team working from two real computers have not been done yet. [Acceptance](docs/acceptance.md) records what has been tried, both ways.

## Learn more

- [Installation](docs/installation.md): what the installer does, how it brings the companion skills, and how to update, roll back or remove.
- [The desk](docs/the-desk.md): read, change and finish a training.
- [The runner](docs/runner.md): making a training on the page, from a form to its finished files, the slide deck included. How a team shares one workspace, takes over, hands over and publishes.
- [The page](docs/page.md): what needs you, every training and this computer's readiness in your browser, and approval that only you can give.
- [How it works](docs/how-it-works.md): the stages, approvals, how changes affect later work, and the files in a training folder.
- [Scenarios and Yoodli](docs/scenarios-and-yoodli.md): the scenario format, and building a roleplay in Yoodli.
- [Google Docs](docs/google-docs.md): sending the learner guide or the brief to a Google Doc for review, and bringing the edits back.
- [Team hub](docs/team-hub.md): sharing finished trainings from a conversation, and reusing your team's scenarios, audiences and research.
- [Development](docs/development.md): the repository, tests, and how to change Training Studio.
- [Design](docs/superpowers/specs/2026-10-12-training-studio-core-pipeline-design.md) and [the runner's design](docs/superpowers/specs/2026-10-13-studio-runner-design.md): the first designs, kept as history. [The runner](docs/runner.md) describes the studio as it is now.

## Licence

[MIT](LICENSE).

Saved older work and its retained paths are described in [saved work compatibility](../../docs/saved-work-compatibility.md).
