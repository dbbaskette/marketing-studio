# Install Marketing Studio

Use `install.sh` in the product's root folder. Marketing Studio installs all
three studios; each individual download installs only that studio. Builders use
`package.sh` in the same source folder. See the [four-product command table](packaging.md)
for the complete, consistent layout and local bundles with brand and private tools.

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

Platform downloads include private Python and Node runtimes, pinned Harness Research
and Harness Slides, and the slide engine's production JavaScript dependencies. Setup
copies them into versioned installation folders. It does not run npm, fetch companion
repositories, install both assistants, or modify shell startup files. No system Python,
Node, npm, pip, Homebrew, or compiler is needed for this path. Standard operating-system
libraries are still required; the bundle is not a container image.

**Git and one signed-in assistant remain external requirements.** Setup reuses existing
Git; if missing, it offers a system package-manager install. Choose Codex or Claude Code
with `--target codex` or `--target claude`. The default detects one existing CLI, preferring
Codex when both exist; if neither exists, it installs the Codex skill integration and
reports that an assistant must be installed and signed in before work can start.
Use `--target both` only when you want both skill integrations. The bundled installer
never installs assistant software or signs into a service.

The same private runtimes support each studio's independent launcher. Deleting the
unpacked download does not remove the installed runtimes. Existing workspaces and
shared settings stay where they are. Companion installations use the upstream shared
locations, locks, version folders, and discovery links. Unrelated skills are preserved;
newer independently installed companions are kept. An installation failure restores
recorded pointers. Rollback restores previous suite, studio and companion pointers;
retained version folders remain available.

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
runtime archive and companion source pin, installs only production npm dependencies
with lifecycle scripts disabled, and includes dependency license notices. Private
runtime locks are in `pins/runtimes.json`. Companion requirements and exact release
locks are in `pins/companions.json`.

Companions accept minimum versions, with `requirement: ">=0.9.5"` for Harness Research
and `requirement: ">=0.14.1"` for Harness Slides. The accompanying `version`, `commit`,
and `sha256` describe the exact source used for a release bundle. Refresh those locks
explicitly before building a new set of platform downloads:

```sh
python3 scripts/update_companions.py --check
python3 scripts/update_companions.py
```

The refresh selects the newest stable numeric Git tag satisfying the requirement,
resolves annotated tags to commits, verifies the package version and entry, and records
a source checksum. It never runs an installer or modifies installed skills. A moved
locked tag, mismatched package, unsafe source, or failed resolution leaves the lock
unchanged. Normal bundle builds reuse the exact saved lock, so all platform builds can
use the same inputs.

An explicit source companion install/update resolves requirements afresh, asks before
fetching source or running installers, then records the selected version, commit and
checksum. `--companions skip`, noninteractive unapproved installs, offline bundle
installation, status checks and opening studios do not perform this resolution.
Stable numeric tags are eligible; branches and prerelease tags are ignored. Removing
a requirement retains legacy exact-lock behavior. Newer installed releases are never
downgraded. Private Python and Node downloads remain exact and checksum-verified.

```sh
python3 scripts/build_bundles.py --platform macos-arm64
python3 scripts/build_bundles.py --platform macos-x64
python3 scripts/build_bundles.py --platform linux-arm64
python3 scripts/build_bundles.py --platform linux-x64
```

Each command produces a full bundle, three individual studio bundles, and SHA-256
sidecars under `dist/`. Use `--studios presentation` to build one selection instead.
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
