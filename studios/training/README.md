# Training Studio

Training Studio turns a topic into training material. You give it a subject, it researches it, and it builds the material with you one stage at a time. On the page, its review level decides where it stops for your decision; see [review levels](docs/runner.md#review-levels).

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

You can make a training in either of two ways. Both use the same file formats. The page follows your saved review preference; a conversation keeps its explicit checkpoints.

| | On the page | In a conversation |
| --- | --- | --- |
| How you start | Open Training Studio and fill in a short form | Ask your assistant for a training, in a folder of your own |
| Who does the work | The runner starts an assistant for each step by itself | Your assistant, in the conversation |
| Where you approve | On a page in your browser | In the conversation, or on the page if you choose |
| Working with a team | Built in: your team shares one workspace | Through a [team hub](docs/team-hub.md) |
| Best for | Getting a training made while you get on with other things | Steering each step closely |

Start on the page for a guided workflow, or use a conversation when you want to steer each stage closely.

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

## Your first training, on the page

**1. Open Training Studio.** On a Mac, double-click "Open Training Studio" in the Applications folder inside your home folder. On any system, run the line the installer printed:

```bash
sh ~/.local/share/training-studio/studio
```

A terminal window opens and the page opens in your browser. Leave the window open while you work.

**2. Set it up, once.** Say where trainings are kept: a folder on this computer to try things out, or a git repository your team shares. The page checks each answer as you give it. If you use Presentation Studio or Blog Studio too, the answers they share, such as the team repository and the agent, are kept in one place for all of them, so a change in one studio is a change in all three (see [the shared studios config](docs/runner.md#shared-studios-config)).

**3. Press "New training".** Describe what learners should be able to do and what they know already. Choose the materials: a guide, reference brief, deck, practice, or a combination. Set the learner's time and choose where the research looks: your documents, your sites (a list of web addresses you keep in Shared settings) and/or the public web. The final summary shows the materials and review preference before you start. Depth, extra copies and assistant settings are optional details.

**4. Review what needs you.** Read the teaching plan and materials when the page asks, or request changes in your own words. Balanced and Automatic draft continue intermediate work according to their saved policy; Step by step asks at each stage. Completed materials stay ahead of the optional production log. You can close the page while it works and come back later.

See [the runner](docs/runner.md) for every step, the slide deck, working as a team, and what it guarantees.

## Your first training, in a conversation

**1. Make a folder for the topic.** One folder is one training. Do not use the Training Studio folder you downloaded.

```bash
mkdir valkey-training
cd valkey-training
```

**2. Add anything you already have.** Put source documents in the folder if you want the research to use them. If you already know the practice situation you want, write it as `scenario.md` (see [writing a scenario](#writing-your-own-scenario)). Both are optional.

**3. Start your assistant in that folder and ask for the training.** Run `claude` or `codex`, then say, for example:

> Use training-studio to build a 101 training on Valkey for teams running Redis, with a competitive brief.

**4. Answer a few questions.** It asks about the audience, what they already know, which levels you want, whether the brief is about one product or a comparison, and which of your documents to use. If you want the learner guide and the brief kept as Google Docs, or as Word files, say so here; by default it makes neither.

**5. Review each stage.** It stops seven times and waits for you:

| It shows you | What to look for |
| --- | --- |
| The research questions | Are these the right things to find out? |
| The research findings | What was confirmed, and what could not be |
| The blueprint | Are these the right objectives, at the right size? |
| The learner guide | Does it teach what the blueprint promises? |
| The brief | Is it honest about weaknesses as well as strengths? |
| The deck | Does it cover every objective? |
| The scenarios | Is this the conversation you want people to practise? |

At each stop you can approve it, ask for changes, or skip that stage. What you were shown, and what you decided, is also saved under `reviews/` in your folder.

You decide in the conversation, by telling your assistant. If you would rather decide on [the page](docs/desk.md), where the document is laid out to read and your assistant cannot approve anything for you, say so when you start.

**6. Find your files.** They are ordinary files: `document.md`, `product-brief.md` or `competitive-brief.md`, the deck, and `scenario.md`, in a folder for each level such as `101/`. If you chose Google Docs or Word copies, the guide and the brief are there too. If you asked for Yoodli scenarios there is a `yoodli/` folder too. `README.md` at the top of your training folder lists everything and says whether the training is complete. [How it works](docs/how-it-works.md#the-training-folder) describes every file.

### Things you can say

- "Where are we?" shows the current stage and what is waiting on you.
- "Is it done?" checks the whole training and lists anything missing.
- "Redo the deck." rebuilds one stage.
- "Skip the deck." leaves a stage out.
- "Just the document." builds only the learner guide.
- "Add a scenario." adds another practice situation.
- "More research on licensing." extends the research.
- "Put the guide in a Google Doc." sends the learner guide or the brief out for review. "Pull the Google Doc." brings the edits back.
- "Keep the guide and the brief in Google Docs." does that for every one from now on. "Make Word copies too." adds Word files. Neither is made unless you ask.
- "What trainings do I have?" lists the trainings on this computer.
- "Open the page." shows what needs you, and every training, in your browser.
- "I want to approve on the page." moves the decisions for this training to that page. From then on only you can approve a stage, there.
- "Publish this to the team hub." shares what you have approved with your team, through a private git repository you control.
- "What is in the hub about Redis?" finds scenarios, audiences and research your team has shared, to reuse in a new training.

### Coming back later

Start your assistant in the same folder and ask for the training again. It picks up where it stopped.

You can edit any file yourself. The next time you ask, Training Studio notices the change, marks anything built from that file as out of date, and asks whether to rebuild it or keep it.

To carry on a training on the page instead, open it there and press "Run this from here". See [bringing a training in](docs/runner.md#bringing-a-training-in).

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

## If something goes wrong

| What you see | What it means |
| --- | --- |
| It stops at research and names harness-research | That skill is not installed. In the Training Studio folder you downloaded, run `sh installer/install.sh --companions install` |
| The deck is "unavailable" | harness-slides is not installed. Everything else still works. The same command installs it |
| The page says the deck needs something | This computer is missing part of what a deck needs. The Status screen says what, and how to get it |
| A Word copy is "unavailable" | You asked for Word copies and no converter was found. Installing [pandoc](https://pandoc.org) fixes it |
| Something is "stale" | A file it was built from has changed. Ask to rebuild it, or say it is fine as it is |
| It refuses to start in a folder | The folder already holds files with the names it uses, or it is the Training Studio folder you downloaded. Use a new folder |
| The page does not work | Open the link exactly as the terminal printed it, and keep that window open. The part after `#` is a key |

## Status

Training Studio is early, so expect rough edges and please [report them](https://github.com/dbbaskette/marketing-studio/issues).

The programs that track your files, and the runner behind the page, have automated tests. A whole training has been made on the page, from the form to its finished files, and another as far as its slide deck. A full run through every stage in a conversation, a roleplay built in Yoodli, and a team working from two real computers have not been done yet. [Acceptance](docs/acceptance.md) records what has been tried, both ways.

## Learn more

- [Installation](docs/installation.md): what the installer does, how it brings the companion skills, and how to update, roll back or remove.
- [The runner](docs/runner.md): making a training on the page, from a form to its finished files, the slide deck included. How a team shares one workspace, takes over, hands over and publishes.
- [The page](docs/desk.md): what needs you, every training and this computer's readiness in your browser, and approval that only you can give.
- [How it works](docs/how-it-works.md): the stages, approvals, what "stale" means, and the files in a training folder.
- [Scenarios and Yoodli](docs/scenarios-and-yoodli.md): the scenario format, and building a roleplay in Yoodli.
- [Google Docs](docs/google-docs.md): sending the learner guide or the brief to a Google Doc for review, and bringing the edits back.
- [Team hub](docs/team-hub.md): sharing finished trainings from a conversation, and reusing your team's scenarios, audiences and research.
- [Development](docs/development.md): the repository, tests, and how to change Training Studio.
- [Design](docs/superpowers/specs/2026-10-12-training-studio-core-pipeline-design.md) and [the runner's design](docs/superpowers/specs/2026-10-13-studio-runner-design.md): the first designs, kept as history. [The runner](docs/runner.md) describes the studio as it is now.

## Licence

[MIT](LICENSE).
