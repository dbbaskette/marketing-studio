![Marketing Studio — one workspace for Blog Studio, Presentation Studio, and Training Studio](docs/assets/marketing-studio-header.png)

<p align="center">
  <strong>From your first idea to a blog, a deck, or a training.</strong><br>
  Set up your tools once. Open the studio you need. Keep control of every decision.
</p>

<p align="center">
  <a href="https://github.com/dbbaskette/marketing-studio/releases/latest"><strong>Download</strong></a> &nbsp; • &nbsp;
  <a href="#get-started">Get started</a> &nbsp; • &nbsp;
  <a href="#a-command-for-everyday-work">CLI guide</a> &nbsp; • &nbsp;
  <a href="docs/architecture.md">How it works</a>
</p>

<p align="center">
  <img alt="Local first" src="https://img.shields.io/badge/Local-first-0a66e4?style=flat-square">
  <img alt="Python 3.11 or newer" src="https://img.shields.io/badge/Python-3.11%2B-3776ab?style=flat-square">
  <img alt="macOS and Linux" src="https://img.shields.io/badge/macOS_%26_Linux-supported-1b7032?style=flat-square">
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/License-MIT-565a69?style=flat-square"></a>
</p>

---

## Three studios. One place to begin.

Marketing Studio is the home for your writing and presentation tools. It holds
shared settings and opens the right studio for the job. Each studio also has its
own launcher and can be installed on its own.

| You want to… | Open | What you work on |
| :--- | :--- | :--- |
| Turn an idea into a blog in your voice | **[Blog Studio](studios/blog)** | Research, outline, draft, review, and a publication handoff |
| Build a researched presentation in your brand | **[Presentation Studio](studios/presentation)** | New decks, existing decks, storyboards, and slide reviews |
| Teach a topic at the right level | **[Training Studio](studios/training)** | Research, teaching plans, learner materials, decks, and practice |

**Your choices carry across the studios:** your name, assistant, work location,
brand, delivery format, and sharing preference. All three studios read the shared
assistant, model and reasoning settings.
Slide previews and your brand skill source are shared too: give a Git repository
address or choose an installed folder. A repository does not require a folder path.
Research and slide tools install at the exact, checksum-verified versions locked in
`pins/companions.json`. An installed copy that meets the minimum requirement
(`>=1.0.0` for Harness Research and `>=0.14.1` for Harness Slides) is kept, so a
source install with current tools needs no network. Newer releases are adopted only
when the locks are refreshed and the research contract tests pass again.
Downloadable bundles include the same exact versions and install offline; opening a
studio never updates its tools automatically.

Quick, Main, and Complex model profiles can be configured once in Shared settings. Every studio saves the resolved choices with new work. [See model routing](docs/shared-setup.md#models-by-task).

## Get started

### 1. Get the installer

**[Choose a download for your computer](https://github.com/dbbaskette/marketing-studio/releases/latest)**.
Look for a versioned platform bundle such as `marketing-studio-4.1.0-macos-arm64.zip`.
Choose `macos-arm64` for Apple Silicon, `macos-x64` for an Intel Mac, or the matching
`linux-arm64` / `linux-x64` build for a Linux computer using glibc.

Unzip it, open Terminal, and run `bash install.sh` from the unpacked folder.
This installs Blog Studio, Presentation Studio and Training Studio together.
Each individual studio download has the same root `install.sh` and installs
only that studio. To build your own downloads, use the matching root `package.sh`;
see [package and install the studios](docs/packaging.md).
This works on macOS and Linux without opening a `.command` file. The macOS
Finder launcher, **installer/Install Marketing Studio.command**, is also available.

**The platform bundle brings its own Python, Node, research tools, and slide engine.**
There is no npm install or compiler setup. The runtimes stay inside the installed
version, so you can delete the downloaded folder afterward.

Bring **Git and one signed-in assistant: Codex or Claude Code**. Setup reuses what
is installed and offers to install Git if missing. It detects one assistant; use
`--target codex` or `--target claude` to choose explicitly. Assistant software and
sign-in stay under your control. Google delivery and slide preview tools are optional;
see the [installation guide](docs/installation.md) for their requirements.

If a release lists only the smaller `*-installer.zip` downloads, those are source
installers: they offer to install Python/Node and fetch shared tools during setup.
The platform bundles are built separately for each operating system and processor.

<details>
<summary><strong>Prefer to install from source?</strong></summary>

```sh
git clone https://github.com/dbbaskette/marketing-studio.git
cd marketing-studio
bash install.sh
```

Install just the studio you want:

```sh
bash install.sh --studios blog --yes
bash install.sh --studios presentation --yes
bash install.sh --studios training --yes
```

Use `--target codex` or `--target claude` to choose one assistant. Add `--yes`
for unattended setup. Assistant CLIs are left untouched by default. Use
`--companions skip` to skip shared tools. `--prerequisites skip` provides an
offline path with no package-manager or assistant installs. Existing work and
settings stay in their current locations.

</details>

### 2. Open Marketing Studio

Double-click **Open Marketing Studio.command** in your **Applications** folder,
or use the installed command:

```sh
marketing-studio
```

The installer puts it in `~/.local/bin`. If your shell cannot find it, run
`~/.local/bin/marketing-studio`, or add that folder to your current terminal:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

Leave the terminal open while you work. Press **Ctrl-C** to stop Marketing Studio
and the studio processes it opened. Studios opened with their own launchers keep
running independently. To keep it running without a terminal, use
`marketing-studio start` instead; see [Start and stop in the background](#start-and-stop-in-the-background).

### 3. Make it yours

The first visit opens a short setup:

1. **You and your assistant.** Your name, assistant, and optional model settings.
2. **Your workspace.** Local Git on this computer, or an existing shared repository.
3. **Brand and delivery.** An optional brand skill, slide previews, and your preferred file format.

Each step saves as you go. Finishing setup prepares installed studios without
starting an assistant job. Later visits take you straight to the studio launch
page. Open a studio and start your first piece of work there.

Complete setup in Marketing Studio **or any individual studio**. The same setup form
is available in each. Once finished, opening another studio takes you straight to
its home page, including a studio installed later. Existing workspaces stay in place.

## A command for everyday work

```sh
marketing-studio open blog
marketing-studio open presentation
marketing-studio open training
```

| Command | What happens |
| :--- | :--- |
| `marketing-studio` | Opens the home page |
| `marketing-studio open presentation` | Opens Presentation Studio; reuses it if already open through Marketing Studio |
| `marketing-studio serve` | Runs the home server in this terminal without opening a browser, for example over SSH |
| `marketing-studio serve --lan` | Enables private phone access on your trusted local network |
| `marketing-studio start --all --lan` | Starts Marketing Studio in the background with every installed studio and phone access |
| `marketing-studio stop --all` | Stops every studio, then Marketing Studio |
| `marketing-studio restart --ts` | Restarts Training Studio; `--all` restarts Marketing Studio too |
| `marketing-studio setup` | Opens shared settings, or first-run setup |
| `marketing-studio status` | Shows each studio's version and folder, marks Git checkout copies, and says whether shared setup is complete |
| `marketing-studio doctor` | Checks the tools on this computer, including that your assistant is installed, without contacting providers |
| `marketing-studio --help` | Shows the command guide |
| `marketing-studio --version` | Shows the installed suite version |

For scripts, add `--json` to `status`, `doctor`, `start`, `stop` or `restart`.

## Start and stop in the background

`marketing-studio start` runs Marketing Studio in the background, so no terminal
has to stay open. Choose studios to start with it, or `--all` for every installed one:

```sh
marketing-studio start                 # Marketing Studio only
marketing-studio start --bs --ts       # also Blog Studio and Training Studio
marketing-studio start --all --lan     # everything, with phone access
marketing-studio stop --ps             # Presentation Studio only
marketing-studio stop --all            # every studio, then Marketing Studio
marketing-studio restart --all         # same phone access and port; restarts the studios that were running
```

Choose studios with `--bs` (Blog Studio), `--ps` (Presentation Studio) and `--ts`
(Training Studio); `-bs`, `--blog` and the like also work, as does putting the
command last: `marketing-studio --all stop`. In a terminal, `start` prints the
private link, and the phone link when phone access is on. Through a pipe or with
`--json` it prints JSON without any key. Its output goes to `home.log` in the
Marketing Studio data folder.

A studio that is running an assistant job is not stopped or restarted: its work so
far would be lost. The command names the job and how long it has run, stops
nothing, and exits with status 1. Wait for the job, or add `--force` to stop it anyway.
`--force` is only needed while an assistant is working; between steps a run is paused
safely and resumes when its studio starts again.

If Marketing Studio stopped abruptly and left a studio running, the next start
stops it, unless it is still running an assistant job; `marketing-studio status`
then shows it, and `marketing-studio stop --all` stops it. Only studios this
Marketing Studio data folder recorded are ever stopped.

## Open it on your phone

Connect your phone and computer to the same **trusted Wi-Fi**, then start:

```sh
marketing-studio start --all --lan
```

Or keep it in this terminal with `marketing-studio serve --lan`.

Open the **private phone link** printed in the terminal. Once setup is complete,
Marketing Studio also shows it under **Continue on your phone**. Launch Blog Studio,
Presentation Studio, or Training Studio there; their links work on your phone too.
The layouts adapt to a narrow screen, with touch controls and readable forms.
Your work, Git repositories, and signed-in assistant stay on the computer.

Network access is off by default. If Marketing Studio is already running, turn it
on with `marketing-studio restart --all --lan`, or stop its terminal with **Ctrl-C**
first. Stopping Marketing Studio (`marketing-studio stop --all`, or Ctrl-C in its
terminal) closes its network listeners and studios. A new session gets new links.
Use only a trusted network: HTTP is unencrypted, and anyone with a private link can
use that studio with your local account's permissions. Do not forward these ports
to the internet.

For address selection, firewall help, and troubleshooting, see
[local-network access](docs/local-network.md).

## Keep your work local. Share when you choose.

**Local Git is the default. A remote repository is optional.** Every studio can
record decisions on this computer without a GitHub account.

With the default work folder, your projects live here:

```text
~/Studios/
├── blog-workspace/blogs/
├── presentation-workspace/presentations/
└── training-workspace/trainings/
```

For collaboration, choose an existing repository in setup. Each studio keeps its
own clone and works in its own content folder. Choose whether to share after each
decision or only when asked. Setup never changes a repository's visibility.

Already using a studio? Its existing workspace stays where it is. Shared choices
are used for new work; existing items retain their saved choices.

Each studio card on the home page says where that studio's work lives: *Connected
to* the shared repository, *Local Git on this computer*, or *Not connected to the
shared repository*. Changing the workspace setting never moves a studio by itself.
When a studio keeps a different workspace, its card offers **Connect**: the studio
joins the repository through its own join, carries its blogs, trainings or decks
over, commits and pushes them, and leaves the earlier workspace in place. A studio
that is working on an assistant job is not connected until that job is done. An
empty repository works too: the first studio to connect creates the branch with its
folder, and the others add theirs beside it.

## Install, update, or step back

All studios ship from this repository with one shared companion pin set. Platform
bundles include the full suite or a selection for an individual studio.
You can install a single studio and use its own launcher without opening Marketing
Studio first.

To update, download and unpack a newer release, then run:

```sh
marketing-studio update --from /path/to/unpacked-release --yes
```

Use the folder containing `installer/`, rather than the ZIP file. Close running
studios before updating; the installer refuses to interrupt active work.

```sh
marketing-studio rollback --yes
marketing-studio uninstall --yes
```

Rollback restores the recorded prior launchers and installation pointers.
Uninstall removes the Marketing Studio launcher and keeps the independently
installed studios, project content, and settings.

## Need a hand?

| What you see | What to do |
| :--- | :--- |
| A studio says **Not installed** | Run the installer for that studio. For a custom checkout, set its folder in **Shared settings → Studio installations**. |
| Git asks who you are | Set `git config --global user.name "Your Name"` and `git config --global user.email "you@example.com"`. |
| A tool is missing | Run `marketing-studio doctor`, then rerun the downloaded setup script to install missing prerequisites. |
| A browser cannot open, for example over SSH | Marketing Studio keeps running and prints why with its private link. Open that link in a browser, or start with `marketing-studio serve`. |
| An assistant cannot start | Open that CLI in your own terminal and complete its sign-in. |
| A studio does not open | The message names its launch log, `~/.local/share/marketing-studio/logs/<studio>.log`, and shows its last lines. The launch before it is kept as `<studio>.previous.log`. |
| Another studio changed a setting | Reload the settings page so you can review the current value before saving. |

Content choices such as a blog’s tone, a deck’s audience, or a training’s level
belong to the work you create. Time and spending limits, notifications, and update
preferences have built-in defaults and remain optional studio settings. Missing
programs, assistant sign-in, or brand skills appear in the studio’s computer check;
finishing setup does not install software or sign you into services. See the
[shared setup guide](docs/shared-setup.md) for the settings shared across studios.

Shared preferences live in `~/.config/studios-config.json`. Sign-in stays with
your assistant, Git, and Google. Marketing Studio does not store authentication
tokens in that preferences file.

<details>
<summary><strong>For contributors: layout, tests, and migration details</strong></summary>

```text
marketing_studio/    Home page and user CLI
studios/blog/       Blog Studio and its native tests
studios/presentation/
studios/training/
core/studio_core/    Shared infrastructure
ui-kit/             Shared page assets
pins/               One companion version set
installer/          Suite and subset installation
```

Python uses the standard library. There is no frontend build step. Node.js is
used by companion tools and JavaScript checks.

```sh
bash scripts/ci/check.sh
python3 scripts/ci/native_acceptance.py
python3 scripts/ci/native_launch_acceptance.py
bash scripts/ci/tart-macos.sh --dry-run
bash scripts/ci/tart-macos.sh
```

Read the [architecture](docs/architecture.md), [installation guide](docs/installation.md), [testing guide](docs/testing.md),
[migration plan](docs/migration-plan.md), and [source provenance](docs/provenance.md).
Use `presentation-studio-package` to regenerate the local Apple Silicon
Presentation Studio bundle with Tanzu Brand and its tools; the
[local packaging guide](docs/local-presentation-bundle.md) covers CLI setup and
local or Git repository configuration for the companion skills and brand.
The studios' Git histories are preserved under their new directories. Unfinished
Blog Studio research work is preserved on a separate migration branch.

</details>

---

<p align="center"><strong>Pick a studio. Make something useful.</strong></p>

Research uses a shared purpose-led report and brief, independently reviewed before
writing or slide work continues. See [research compatibility and the shared helper](docs/research-synthesis.md).

## Update the source checkouts

Copy `sync.cfg.sample` to the ignored `sync.cfg`, then run `bash sync.sh`.
The config chooses the repository URLs and destination directory; the sample puts
Marketing Studio and its related checkouts under `~/Projects/`. Missing checkouts
are cloned, local work is preserved, and failures are reported while the other
updates continue. See [repository sync](docs/repository-sync.md) for all options.
