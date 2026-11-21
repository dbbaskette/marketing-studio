# Install Marketing Studio

Use `install.sh` in the product's root folder. The Marketing Studio release download
installs all four studios: Blog Studio, Presentation Studio, Training Studio and
Infographic Studio. Each individual download, `infographic-studio-installer.zip`
included, installs only that studio. Builders use `package.sh` in the same source
folder; its local Marketing Studio bundle holds Blog Studio, Presentation Studio and
Training Studio only. See the [four-product command table](packaging.md) for the
complete, consistent layout and local bundles with brand and private tools.

## Versioned platform downloads

Choose a platform bundle on the [release page](https://github.com/dbbaskette/marketing-studio/releases).
Its filename includes the suite version and platform, for example
`marketing-studio-4.1.0-macos-arm64.zip`. macOS and Linux each have Apple Silicon/ARM64
and Intel/AMD64 builds. Linux bundles target glibc distributions, not Alpine/musl.
Only publish a platform download after its native acceptance checks pass.

Unpack the ZIP, open Terminal, and run this inside the unpacked folder on macOS
or Linux:

```sh
bash install.sh
```

Every Marketing Studio and studio subset installer includes this top-level shell
entry point. It forwards options to the same installer as
`bash installer/install.sh`, without opening a `.command` file. The macOS Finder
launcher `installer/Install Marketing Studio.command` remains available.

From a consolidated checkout, install a particular studio with
`bash install.sh --studios blog`, `bash install.sh --studios presentation`, or
`bash install.sh --studios training`. Each independent `studios/<name>/`
directory also has its own `install.sh` for its native installer.

Platform downloads include private Python and Node runtimes, Harness Research and
Harness Slides as their `main` was when the download was built, and the slide engine's
production JavaScript dependencies. Setup copies them into versioned installation folders. It does not run npm, fetch companion
repositories, install both assistants, or modify shell startup files. No system Python,
Node, npm, pip, Homebrew, or compiler is needed for this path. Standard operating-system
libraries are still required; the bundle is not a container image.

**Git and one signed-in assistant remain external requirements.** Setup reuses existing
Git; if missing, it offers a system package-manager install. Choose Codex or Claude Code
with `--target codex` or `--target claude`. The default detects one existing CLI, preferring
Codex when both exist; if neither exists, it installs the Codex skill integration and
reports that an assistant must be installed and signed in before work can start.
Use `--target both` only when you want both skill integrations. The bundled installer
never installs assistant software or signs into a service. Shared setup starts with the
assistant recorded here, and `marketing-studio doctor` reports when it is missing.

The same private runtimes support each studio's independent launcher. Deleting the
unpacked download does not remove the installed runtimes. Existing workspaces and
shared settings stay where they are. Companion installations use the upstream shared
locations, version folders, `current` links and discovery links. Unrelated skills are preserved;
newer independently installed companions are kept. An installation failure restores
recorded pointers, and removes nothing.

**One version is kept.** Marketing Studio, each studio and each bundled companion is
installed in its own `versions/` folder, with a `current` link beside it. Every
launcher, command, skill link and saved path names `current`, never the folder it
points at, so an update moves that one link and nothing else needs rewriting. Once an
update has fully succeeded, the installer removes every other folder in each `versions/`
it installed into, and reports what it removed and anything it could not. Nothing can
go on using an older copy, and no old folder is left for you to clean up. Two things
stay: a companion that is newer than the bundled one is left exactly as it is, and an
older Marketing Studio folder is kept while a studio this install did not renew still
opens with the Python inside it, until that studio is next installed. Uninstalling
Marketing Studio from a platform download keeps its `current` link and private
runtime, because the studios open with them.

Since an update keeps one version, `rollback` normally has nothing to return to. It
checks first and changes nothing: "The earlier version is no longer on this computer:
an update keeps only the newest. Install the release you want instead." To go back,
install the release you want. Rollback still works when every earlier folder it would
point at is still there, which happens only when one could not be removed.

You can check prerequisites without installing system software:

```sh
bash install.sh --prerequisites check --target codex --yes
```

Use `--companions skip` to leave installed companion pointers unchanged.
The installer checks the package manifest before copying or activating its contents.
Compare the ZIP's SHA-256 with the release checksum before opening it.

## Optional capabilities

| Capability | Additional tools | When needed |
| --- | --- | --- |
| Google Docs or Google Slides | gcloud and the user's Google sign-in | When choosing Google delivery or rendering |
| PDF source documents in any studio | Poppler's `pdftotext` on the studio process's PATH | To extract selectable text locally; scanned PDFs need a readable text copy |
| Local slide previews | LibreOffice and Poppler | When choosing local slide rendering |
| Google slide previews | Poppler | To turn the rendered PDF into preview images |
| Generated artwork | The selected image provider's setup | Only when requesting generated artwork |

Gemini CLI is not required or installed. Gemini image generation is separate from
Google document access. The optional Gemini web-image provider has its own Python/browser
runtime setup; it is not included or initialized by the normal suite installer. No
provider request, paid job, browser sign-in, or Cloud project is started during setup.

## Source installers

The smaller `*-installer.zip` archives contain source, without private runtimes or
prepared companions. Contributors can also clone the repository. These paths retain
the prerequisite bootstrap and explicitly requested companion downloads:

```sh
bash install.sh --studios blog --target codex
bash install.sh --studios presentation training --target claude
bash install.sh --prerequisites skip --companions skip --yes
```

Source setup requires Python 3.11+, Git, Node 20+ for companions, and npm for preparing
slide dependencies. Missing assistant CLIs are left alone by default. Explicitly use
`--assistants ask` or `--assistants install` to request npm-based assistant provisioning
from a source installer. Installing Claude Code through that route needs Node 22+.

Compatible existing tools are reused. Homebrew is used when available; on macOS its
installer is offered if missing. Linux also supports `apt-get` or `dnf`. Some Linux
repositories provide an older Node release; use a platform bundle to avoid this issue.
No third-party system package repository is silently added. `--prerequisites skip`,
alternate `--home`, `--dry-run`, help, rollback, uninstall and check do not provision
host prerequisites. `--yes` authorizes selected installation steps without prompts;
it does not opt into assistant provisioning.

## Build downloads

Release preparation is a developer operation. It requires Python 3.11+, Git, Node 20+
and npm. It uses a disposable HOME, ignores user npm configuration, verifies every
runtime archive and checks each companion it fetches, installs only production npm
dependencies with lifecycle scripts disabled, and includes dependency license notices.
Private runtime checksums are in `pins/runtimes.json`. The companions are named in
`pins/companions.json`.

**Companions come from `main`.** There are no release tags to choose and nothing is
locked. Each companion names its repository, its `main` branch and the oldest version
Marketing Studio works with: `requirement: ">=1.3.1"` for Harness Research and
`requirement: ">=0.19.0"` for Harness Slides, the first versions reached through their
stable `current` address. That version is a floor and a label only, never what is
installed. Once you agree to it, a missing companion, or one older than its floor, is
installed from `main` as it is then: fetched with no hooks, checked file for file (no
links, its entry and installer where the pin says, a version at or above the floor)
before its own installer runs, and recorded with the commit and checksum it was. A `main`
older than the floor is refused with a sentence that says to try again once it is updated.

An update means that `main` is at another commit than the one installed: a studio's
Update, or `install.py companions --update`, installs `main` again. A copy that meets the
floor is otherwise left alone without looking anything up online, so a source install with
current companions succeeds offline. An offline bundle carries whatever `main` was when it
was built, with that commit and checksum in its record.

To see what each `main` holds before a build, and to run the research contract tests
against Harness Research's `main`:

```sh
python3 scripts/update_companions.py
python3 scripts/ci/research-runtime.py "$TMPDIR/research-runtime"
STUDIO_TEST_RESEARCH_RUNTIME="$TMPDIR/research-runtime" PYTHONPATH=tests python3 -m unittest test_research_contract
```

`update_companions.py` reads where each `main` is, fetches and checks it as an install
would and reports its version and commit. It writes nothing and runs no installer, and it
fails when a `main` is older than its floor.

An explicit source companion install or update asks before looking anything up, fetching
source or running installers. `--companions skip`, noninteractive unapproved installs,
offline bundle installation, status checks and opening studios fetch nothing. Newer
installed copies are never replaced except by an update you ask for. Private Python and
Node downloads remain exact and checksum-verified.

```sh
python3 scripts/build_bundles.py --platform macos-arm64
python3 scripts/build_bundles.py --platform macos-x64
python3 scripts/build_bundles.py --platform linux-arm64
python3 scripts/build_bundles.py --platform linux-x64
```

Each command produces a full bundle with all four studios, four individual studio
bundles (Infographic Studio's included), and SHA-256 sidecars under `dist/`. Use `--studios presentation` to build one selection instead.
The individual Blog Studio bundle includes Harness Research without the slide engine.
The runtime is platform-specific. Prepared slide dependencies must be pure JavaScript;
the builder refuses native Node extensions rather than silently shipping binaries for
the build machine. Native acceptance remains necessary for every published platform.

Without `--platform`, the builder produces the existing source installer archives.
Builds and tests do not publish releases or change the installed studios.

Runtime sources: [Node downloads](https://nodejs.org/en/download),
[Python standalone distributions](https://github.com/astral-sh/python-build-standalone),
and [Python distribution format](https://github.com/astral-sh/python-build-standalone/blob/main/docs/distributions.rst).

## Installation logs

Every installation attempt keeps a timestamped, private log under
`~/.local/state/marketing-studio/logs/`. Terminal prints its full path at the
start and end, including on failure. This applies to Marketing Studio, each
independent studio, and online/offline local bundles. `--home PATH` puts the log
under that home. Help and dry runs do not create logs.

The log includes the shell bootstrap's console transcript, Python version and
executable, installer subprocess commands and working directories, captured output,
exit statuses, timeouts, and final result. Nested installers share one file;
retries create a new file. JSON output stays separate from diagnostic messages.
Logs are outside verified bundle contents and remain after rollback or uninstall.
Commands mask recognized credential arguments; environments and subprocess stdin
are not recorded. Tool console output and local paths can contain private details,
so review the log before sharing it. Logs are readable only by the installing user.

Workspace setup runs after installation. When Git fails without any error output,
the setup page now names the Git command and exit status or terminating signal.
It also names a private metadata file under the affected studio's data folder,
`~/.local/share/<studio>-studio/logs/git-*.json`. That record contains the Git
executable and working directory, without command arguments or document content.

Local bundles also include an offline Git check:

```sh
bash diagnose-git.sh
# Or after installation:
bash "$HOME/Applications/Diagnose Presentation Studio Git.sh"
```

It tests the installed private Git in a disposable repository with a synthetic
identity, hooks and commit signing disabled. It makes no network requests and
does not change existing workspaces, Git configuration, or studio settings. Its
private report goes beside the installation logs. A passing check establishes
that Git can start, initialize, and commit; it does not check an existing
workspace's hooks, signing setup, identity, or repository permissions.

Infographic Studio is the fourth native selection (`--studios infographic`, `--is`
for start/stop/restart, or `open infographic`). Its standalone launch opens shared
setup when needed and preserves existing workspaces. It uses local supplied-information
storage in this release, even when the other studios share a team repository.
Prepared supported-platform packages include its pinned renderer. Its own pipeline
installs no image SDK or Research/Slides companion; an explicitly selected brand
add-on can have separate prerequisites. See its [setup and usage guide](../studios/infographic/README.md).
