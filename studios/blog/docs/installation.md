# Install Blog Studio

Blog Studio runs in your existing local Codex or Claude Code chat. Install once; new writing tasks check for updated writing instructions automatically. Your drafts and voices stay in their own workspace.

## Guided Mac setup

1. Sign into GitHub with an account that has access to the private [Blog Studio repository](https://github.com/dbbaskette/blog-studio). Download [blog-studio-installer.zip](../dist/blog-studio-installer.zip) using **Download raw file** on its GitHub page. A team administrator can also distribute this trusted ZIP privately. Downloading the repository ZIP through **Code → Download ZIP** works too.
2. Expand the ZIP. Open `blog-studio-setup/installer/Install Blog Studio.command` (or `installer/Install Blog Studio.command` inside the repository download). Setup opens a terminal with simple choices. Use your organization's usual approval process if macOS blocks an unsigned downloaded launcher; this first release is not a signed app.
3. Choose **Codex**, **Claude Code**, or **Both**, review the displayed destinations, then continue.
4. Setup checks Git, Python, and access to this exact private repository. It reuses working Git authentication. If needed, choose GitHub CLI browser sign-in using your own account. This can configure Git's credential helper for github.com. If GitHub CLI is absent and you already use Homebrew, setup offers to install it with your permission.
5. Open a **new local harness session** and invoke Blog Studio: `$blog-studio` in Codex or `/blog-studio` in Claude Code. Try: “Help me build an outline from my notes. Offer source and voice options, and stop at the outline.”

Setup verifies the local files and links and runs the helpers in a disposable workspace. Confirming discovery and an actual writing flow happens in the harness. Claude Cowork and cloud-hosted sessions are outside this installer’s scope.

## If a prerequisite is missing

| Requirement | What to do |
| --- | --- |
| Local Codex or Claude Code | Install/open your chosen harness. Setup does not change model/provider settings. |
| Python 3.11 or later | Use the [Python macOS installer](https://www.python.org/downloads/macos/), then reopen setup. |
| Git | Follow the [Git macOS installation instructions](https://git-scm.com/download/mac), then reopen setup. |
| GitHub repository access | Ask the repository owner for access, then sign into your own account. Signing in does not grant access by itself. |
| Optional GitHub CLI | Use [GitHub CLI installation](https://cli.github.com/) if browser sign-in is needed and Homebrew is unavailable. Existing Git credentials are sufficient. |

The launcher detects missing tools before handing off to Python. Python and Git installation are guided vendor steps, not unattended installers. No Node installation, model API key, Google account, Word converter, or running web server is required for core writing.

## Where setup puts things

| Location | Purpose |
| --- | --- |
| `~/.agents/skills/blog-studio` | Codex discovery link |
| `~/.claude/skills/blog-studio` | Claude Code discovery link; honors `CLAUDE_CONFIG_DIR` |
| `~/.local/share/blog-studio/versions/` | Verified bootstrap and executable helper versions |
| `~/.local/share/blog-studio/current` | Shared active runtime link |
| `<writing-project>/.blog-studio/` | Default author workspace: sources, voices, articles, reviews, pinned guidance |

Both harnesses can use the same runtime. Existing unmanaged skill folders require an explicit replacement choice and a preserved backup. A legacy copy under `~/.codex/skills/blog-studio` must be moved to a backup outside discovery roots first to avoid duplicate discovery. A custom configuration that points both harnesses at the same folder is rejected.

## How automatic updates work

At the start of a new writing task, the installed helper quietly fetches approved `main`, records the exact commit, and saves a read-only guidance snapshot. Only a short status and file paths return to the model; Git progress and the downloaded library do not become conversation context. The assistant reads the relevant guidance progressively.

An existing article keeps its guidance task and runtime path. Resume reuses that pin. Adopting newer guidance is an explicit author choice and makes prior reviews stale when the revision changes. If a new-task fetch fails, setup does not pretend the guidance is current: the author can explicitly choose an intact cached task or resolve access first.

Writing instructions, templates, and rubrics update from the repository without reinstallation. Executable helpers and the bootstrap update only when you rerun an intact installer bundle. Incompatible guidance requests a runtime update. Downloaded scripts are never executed by the refresh helper.

## Check, update, repair, roll back, or remove

Keep the installer download, or download a fresh trusted copy when updating. Advanced commands below run from its top-level folder; the Mac launcher accepts the same arguments.

```sh
python3 installer/install.py check
python3 installer/install.py install --target both
python3 installer/install.py repair --target both
python3 installer/install.py rollback
python3 installer/install.py uninstall --target both
```

- **Check** inspects tools, repository access, links, and runtime integrity. `check --offline` avoids the network.
- **Install again** updates to the bundle’s verified runtime; an unchanged install is idempotent.
- **Repair** stages an intact replacement for a damaged runtime/configuration and restores missing owned discovery links. It preserves the damaged version for diagnosis.
- **Rollback** activates the previous intact runtime for all shared discovery links. It verifies that version before switching. A damaged previous version cannot be activated.
- **Uninstall** removes only the selected owned discovery links. It retains drafts, voices, caches, backups, runtime versions, Python, Git, and GitHub CLI.

For an existing unmanaged folder, review it first, then explicitly use `install --replace` to preserve it in a sibling backup before replacement. `--yes` skips confirmation but does not authorize replacement or install missing shared tools. `--dry-run` reports intended targets without installing. `--json` provides diagnostics. `--home` and `--root` are advanced fixture/custom-location options.

`install --offline` skips only the repository-access check. It installs the bootstrap, which still needs a verified cached task or network access to begin writing. For a completely offline first use, expand the separate [full skill ZIP](../dist/blog-studio.zip) and manually install its complete `blog-studio` folder; that package does not auto-refresh.

## Validation status

Disposable-home and local-Git tests cover both target layouts, task pins, updates, repair, rollback, access failures, backups, and draft preservation. CI exercises supported Python versions on macOS and Linux. A clean-Mac double-click/sign-in pilot and live discovery/writing in both harnesses remain to be completed; fixture tests do not establish those results. Windows link behavior and a Windows launcher are not validated.

See [troubleshooting](troubleshooting.md), [package notes](../PACKAGE.md), and the [Google Docs next phase](google-docs-roadmap.md).
