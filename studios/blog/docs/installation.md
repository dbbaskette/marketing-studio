# Install Blog Studio

Blog Studio runs in your existing local Codex or Claude Code chat. Install once; new writing tasks check for updated writing instructions automatically. Your drafts and voices stay in their own workspace.

## Guided Mac setup

1. Sign into GitHub with an account that has access to the private [Blog Studio repository](https://github.com/dbbaskette/blog-studio). Download [blog-studio-installer.zip](../dist/blog-studio-installer.zip) using **Download raw file** on its GitHub page. A team administrator can also distribute this trusted ZIP privately. Downloading the repository ZIP through **Code → Download ZIP** works too.
2. Expand the ZIP. Open `blog-studio-setup/installer/Install Blog Studio.command` (or `installer/Install Blog Studio.command` inside the repository download). Setup opens a terminal with simple choices. Use your organization's usual approval process if macOS blocks an unsigned downloaded launcher; this first release is not a signed app.
3. Choose **Codex**, **Claude Code**, or **Both**, review the displayed destinations, then continue.
4. Setup checks Git, Python, and access to this exact private repository. It reuses working Git authentication. If needed, choose GitHub CLI browser sign-in using your own account. This can configure Git's credential helper for github.com. If GitHub CLI is absent and you already use Homebrew, setup offers to install it with your permission.
5. Open a **new local harness session** and invoke Blog Studio: `$blog-studio` in Codex or `/blog-studio` in Claude Code. Try: “Help me build an outline from my notes. Offer source and voice options, and stop at the outline.”

Setup verifies the local files and links and runs the helpers in a disposable workspace. Confirming discovery and an actual writing flow happens in the harness. Claude Cowork and cloud-hosted sessions are outside this installer’s scope.

## Install from an existing shell

If your company permits shell scripts but blocks opening `.command` launchers, download and expand the same trusted installer ZIP. Open your approved terminal, change into the expanded `blog-studio-setup` folder, and run:

```sh
sh installer/install.sh
```

Choose Codex, Claude Code, or both in the guided prompts. To select both in advance:

```sh
sh installer/install.sh install --target both
```

The script runs in your current terminal and returns when setup finishes. It finds Python 3.11+ (including common Homebrew locations) and runs the same bundled installer, with the same private repository checks, installation locations, updates, and backups. Keep the entire expanded bundle together: `install.sh` is an entry point, not a standalone download. It also works from a source checkout or with a quoted absolute path from any working directory:

```sh
sh "/path with spaces/blog-studio-setup/installer/install.sh" check --offline
```

No `sudo`, executable-bit change, or terminal auto-launch is required. If your organization also blocks shell scripts or the required tools, use its normal IT approval process; this option does not change device security settings. Installation still requires Python and Git. Local Codex and Claude Code CLIs are installed and signed into separately.

## If a prerequisite is missing

| Requirement | What to do |
| --- | --- |
| Local Codex or Claude Code | Install/open your chosen harness. Setup does not change model/provider settings. |
| Python 3.11 or later | Use the [Python macOS installer](https://www.python.org/downloads/macos/), then reopen setup. |
| Git | Follow the [Git macOS installation instructions](https://git-scm.com/download/mac), then reopen setup. |
| GitHub repository access | Ask the repository owner for access, then sign into your own account. Signing in does not grant access by itself. |
| Optional GitHub CLI | Use [GitHub CLI installation](https://cli.github.com/) if browser sign-in is needed and Homebrew is unavailable. Existing Git credentials are sufficient for guidance refresh; Team Hub operations require authenticated GitHub CLI. |

The shell entry point detects a supported Python; the Python installer checks Git and repository access before installation. Python and Git installation are guided vendor steps, not unattended installers. No Node installation, model API key, Google account, Word converter, or running web server is required for core writing.

## Where setup puts things

| Location | Purpose |
| --- | --- |
| `~/.agents/skills/blog-studio` | Codex discovery link |
| `~/.claude/skills/blog-studio` | Claude Code discovery link; honors `CLAUDE_CONFIG_DIR` |
| `~/.local/share/blog-studio/versions/` | Verified bootstrap and executable helper versions |
| `~/.local/share/blog-studio/current` | Shared active runtime link |
| `<writing-project>/.blog-studio/` | Default author workspace: sources, voices, articles, reviews, pinned guidance |

Both harnesses can use the same runtime. Existing unmanaged skill folders require an explicit replacement choice and a preserved backup. A legacy copy under `~/.codex/skills/blog-studio` must be moved to a backup outside discovery roots first to avoid duplicate discovery. A custom configuration that points both harnesses at the same folder is rejected.

## Enable shared Team Hub work

Update to the **1.3.0** bundle using Install again, then ask Blog Studio to create or join the specific team repository. The GitHub provider requires authenticated GitHub CLI as well as Git. Team access is managed outside setup. Hubs default to `~/.local/share/blog-studio/hubs/`, separately from runtime versions and local writing projections. No repo is created or content uploaded by installation. See [Team Hub usage](team-hub.md).

## How automatic updates work

At the start of a new writing task, the installed helper quietly fetches approved `main`, records the exact commit, and saves a read-only guidance snapshot. Only a short status and file paths return to the model; Git progress and the downloaded library do not become conversation context. The assistant reads the relevant guidance progressively.

An existing article keeps its guidance task and runtime path. Resume reuses that pin. Adopting newer guidance is an explicit author choice and makes prior reviews stale when the revision changes. If a new-task fetch fails, setup does not pretend the guidance is current: the author can explicitly choose an intact cached task or resolve access first.

Writing instructions, templates, and rubrics update from the repository without reinstallation. Executable helpers and the bootstrap update only when you rerun an intact installer bundle. Incompatible guidance requests a runtime update. Downloaded scripts are never executed by the refresh helper.

## Check, update, repair, roll back, or remove

Keep the installer download, or download a fresh trusted copy when updating. Advanced commands below run from its top-level folder; both launchers accept the same arguments. `sh installer/install.sh` is the recommended command for an existing shell; direct Python invocation remains supported.

```sh
sh installer/install.sh check
sh installer/install.sh install --target both
sh installer/install.sh repair --target both
sh installer/install.sh rollback
sh installer/install.sh uninstall --target both
```

- **Check** inspects tools, repository access, links, and runtime integrity. `check --offline` avoids the network.
- **Install again** updates to the bundle’s verified runtime; an unchanged install is idempotent.
- **Repair** stages an intact replacement for a damaged runtime/configuration and restores missing owned discovery links. It preserves the damaged version for diagnosis.
- **Rollback** activates the previous intact runtime for all shared discovery links. It verifies that version before switching. A damaged previous version cannot be activated.
- **Uninstall** removes only the selected owned discovery links. It retains drafts, voices, caches, backups, runtime versions, Python, Git, and GitHub CLI.

For an existing unmanaged folder, review it first, then explicitly use `install --replace` to preserve it in a sibling backup before replacement. `--yes` skips confirmation but does not authorize replacement or install missing shared tools. `--dry-run` reports intended targets without installing. `--json` provides diagnostics. `--home` and `--root` are advanced fixture/custom-location options.

`install --offline` skips only the repository-access check. It installs the bootstrap, which still needs a verified cached task or network access to begin writing. For a completely offline first use, expand the separate [full skill ZIP](../dist/blog-studio.zip) and manually install its complete `blog-studio` folder; that package does not auto-refresh.

## Validation status

Disposable-home and local-Git tests cover both target layouts, task pins, updates, repair, rollback, access failures, backups, and draft preservation. CI exercises supported Python versions on macOS and Linux. A fresh Tart macOS 27 clone passed 91 tests plus real CLI installation for Codex-only, Claude-only and both targets. It exposed a GUI-PATH Python discovery bug that is fixed. Full browser sign-in and signed-in discovery/writing in both harnesses remain to be completed. See the [dated pilot record](i4-m4-m5-validation.md); automated placement is not live discovery. Windows link behavior and a Windows launcher are not validated.

See [troubleshooting](troubleshooting.md), [package notes](../PACKAGE.md), and the [Google Docs workflows](google-docs.md).

## Repeat the isolated Mac checks

From the source checkout, maintainers can run `bash scripts/ci/tart-macos.sh` with the existing
`macos-test-suite` runner. Set `MACOS_TEST_SUITE` to its checkout and `TART_BASE`
to a stopped prepared base if different from the defaults. The guest needs
Python 3.11+, Git and Node (Node tests the optional prompt generator). The wrapper
clones the base, mounts source read-only, runs in a guest copy, and retains results
and the stopped clone. It never mounts host credentials or starts model calls.
The guest result proves the listed automated checks only; live sign-in, trust
consent and conversational checks retain their own evidence.

## Optional Google Docs

Runtime 1.3.0 includes readiness, article discovery/context controls, and local Google transfer checkpoints. Use the harness’s existing connected Google Drive tools when requested; core setup needs no Google login or extra CLI. See [Google Docs usage](google-docs.md). CLI sign-ins and core writing flows have been tested in Tart; live Google provider verification still needs a selected test document. See [validation evidence](usability-validation.md).

## Optional Google Docs access

The installer ZIP includes `installer/google-setup.sh`. Use `--install-cli` to
install gcloud through existing approved Homebrew, then `--login` for Google
Drive browser consent and `--check` for a read-only access check. The equivalent
login is `gcloud auth login --enable-gdrive-access --force`. It can change the
active gcloud account. No custom OAuth client, Cloud project or billing setup
is required. Default installation skips Google; `--google-docs gcloud` opts in
after setup, while `--google-docs gcloud-check` checks only. See [Google Docs](google-docs.md)
for native editing limits and document round-trip verification.

### Update for formatted Google editing

Runtime 1.5 adds DOCX/Markdown snapshot storage and guarded paragraph wording
patches. Run the new installer bundle once with the same targets; existing
credentials, workspace and rollback version remain in place. Guidance refresh
alone does not add runtime helpers. Members of a Hub receiving formatted snapshots
need 1.5 before contributing, so older clients cannot silently drop those files.

### Update for Google review suggestions

Runtime **1.9** adds **“Push as suggestions,”** automatic checks of the latest
linked Doc before submission, and separate storage of pending suggestions on
pull. Download the current trusted installer bundle, run Install again for your
existing targets, and start a new Codex or Claude Code session. Writing, account
credentials and saved guidance pins remain in place. No additional CLI is needed
beyond the existing Google connection.

Members contributing to a Hub containing the new review snapshots need runtime
1.9 so older clients cannot drop the accepted-text evidence. See the
[Google workflow](google-docs.md) and [validation record](google-suggestions-validation.md).

## When Google suggestions are unavailable

Keep using **“Push as suggestions.”** If your connector lacks the needed option,
Blog Studio can use its already configured gcloud connection. If native suggestions
are still unavailable, it posts readable review comments and tells you which mode
was used. Ordinary document comments appear in **All Comments**, with the section,
current wording, proposed wording and reason; they do not have Accept/Reject buttons.
Minor fixes in one paragraph can share a comment while keeping individual numbers.

Say **“Show review edits”**, then **“Apply edits 2 and 4”** to choose changes.
Blog Studio checks current wording, applies only your selection, verifies formatting,
and resolves completed comments. A resolved comment alone never means approval.
Afterward, say **“Pull from Google Docs.”** Runtime **1.10** provides this workflow;
run the current installer once and start a new session. A hosted connector's
missing option does not require changing the document's settings.

## Runtime 1.11: start from a Google Doc

Run the current installer again to update executable helpers. “Start from this
Google Doc: [link]” now saves the original, draft, formatted snapshot and working
Doc link in one local operation. Future proofreading suggestions target that Doc.
The update also handles review targets after inline charts, Google’s native anchor
and inherited-style representations, actionable authorization failures, and Hub
filesystem failures after a successful local save. A previous formatting baseline
may need a fresh inspected pull; the updater does not rewrite review receipts.
