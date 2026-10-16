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
brand, delivery format, and sharing preference. Presentation Studio and Training
Studio also read the shared model and reasoning settings. Blog Studio uses the
model configured in your assistant CLI.

## Get started

### 1. Get the installer

**[Download the latest installer](https://github.com/dbbaskette/marketing-studio/releases/latest/download/marketing-studio-installer.zip)**,
unzip it, and open **installer/Install Marketing Studio.command** on macOS.
On Linux, run `bash installer/install.sh` from the unpacked folder.

**One installer handles the setup.** It checks your computer, offers to install
missing Python, Git, Node.js, and assistant CLIs, then installs your studios and
their shared research and slide tools. Existing compatible tools are reused.
Choose Codex, Claude Code, or both; sign in to your chosen assistant afterward.

On macOS, setup uses Homebrew and offers to install it if needed. On Linux, it
uses an existing Homebrew, `apt-get`, or `dnf`; your package repositories must
provide Python 3.11+ and Node.js 20+. System installs may request your administrator
password. Google delivery is optional; local files work without a Google account.

<details>
<summary><strong>Prefer to install from source?</strong></summary>

```sh
git clone https://github.com/dbbaskette/marketing-studio.git
cd marketing-studio
bash installer/install.sh
```

Install just the studio you want:

```sh
bash installer/install.sh --studios blog --yes
bash installer/install.sh --studios presentation --yes
bash installer/install.sh --studios training --yes
```

Use `--target codex` or `--target claude` to choose one assistant. Add `--yes`
for unattended setup, `--assistants skip` to keep assistant CLIs untouched, or
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
running independently.

### 3. Make it yours

The first visit opens a short setup:

1. **You and your assistant.** Your name, assistant, and optional model settings.
2. **Your workspace.** Local Git on this computer, or an existing shared repository.
3. **Brand and delivery.** An optional brand skill and your preferred file format.

Each step saves as you go. Finishing setup prepares installed studios without
starting an assistant job. Later visits take you straight to the studio launch
page. Open a studio and start your first piece of work there.

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
| `marketing-studio setup` | Opens shared settings, or first-run setup |
| `marketing-studio status` | Shows which studios are installed and whether shared setup is complete |
| `marketing-studio doctor` | Checks the tools on this computer without contacting providers |
| `marketing-studio --help` | Shows the command guide |
| `marketing-studio --version` | Shows the installed suite version |

For scripts, add `--json` to `status` or `doctor`.

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

## Install, update, or step back

All studios ship from this repository with one shared companion pin set. The
release includes the full installer and a separate installer for each studio.
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
| An assistant cannot start | Open that CLI in your own terminal and complete its sign-in. |
| Another studio changed a setting | Reload the settings page so you can review the current value before saving. |

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

Read the [architecture](docs/architecture.md), [testing guide](docs/testing.md),
[migration plan](docs/migration-plan.md), and [source provenance](docs/provenance.md).
The studios' Git histories are preserved under their new directories. Unfinished
Blog Studio research work is preserved on a separate migration branch.

</details>

---

<p align="center"><strong>Pick a studio. Make something useful.</strong></p>
