# Blog Studio setup help

Start with `sh installer/install.sh check` from the expanded installer folder.
It changes nothing and names the next step. Add `--json` when you need details
to share; the output contains paths and versions, never credentials.

## Installing and updating

| What you see | What to do |
| --- | --- |
| “Blog Studio setup requires Python 3.11 or later” | Install Python from [python.org](https://www.python.org/downloads/macos/) and run setup again. Setup looks in the usual Homebrew and python.org locations as well as your `PATH`. |
| macOS will not open `Install Blog Studio.command` | The launcher is an unsigned download. Open Terminal in the `blog-studio-setup` folder and run `sh installer/install.sh`, which does the same thing. If your company also blocks shell scripts, ask IT to approve the installer. |
| “The skill folder is missing” | Run setup from the complete expanded `blog-studio-setup` folder. `install.sh` is an entry point, not a standalone download. |
| “The package inventory is incomplete or changed” or “does not match its recorded hash” | The download is damaged or was edited. Download the installer ZIP again and expand it into a new folder. |
| “An existing skill folder needs a backup before replacement” | Another Blog Studio folder is already in a skill location. Run setup in a terminal and answer yes when it offers to move the folder, or add `--replace`. The folder goes to `~/.local/share/blog-studio/backups/`. |
| “Setup needs an answer but has no interactive terminal” | Setup was started without a terminal, for example by an assistant. Run `sh installer/install.sh install --target both --yes` (or `codex` / `claude`). |
| “Another installer is running” | A second setup is in progress; wait for it. A crashed setup cannot cause this, because the lock ends with the process. |
| Setup was interrupted or the window was closed | Run setup again. It either left the previous version active or completes the switch now. |
| `check` reports damaged files or an invalid configuration | Run `sh installer/install.sh repair` from an intact download. The damaged copy is kept for diagnosis. |
| `check` says the helper Python is missing | The Python recorded at installation was removed or upgraded away. Run `sh installer/install.sh repair` to record a working one. |
| “There is no previous managed version to restore” | Rollback needs an earlier installed version; a first installation has none. |
| Rollback rejects the previous version | Its files were changed after installation. Stay on the current version, or run setup from the installer you want. |
| “A discovery link was changed outside the installer” | Something replaced the link in your tool's skill folder. Setup will not delete what it did not create. Inspect that folder, move it away if you no longer need it, then run setup. |

## In your tool

| What you see | What to do |
| --- | --- |
| Blog Studio is not offered in chat | Open a new local session; tools read skills when a session starts. Then use the tool's skill picker, `$blog-studio` in Codex or `/blog-studio` in Claude Code. `check` shows whether the files are in place, not whether the tool has loaded them. |
| Two Blog Studio entries | A manual copy sits beside the managed one. Run setup and let it move the extra folder to backups. |
| “This guidance needs a newer local Blog Studio runtime. Run the installer update.” | You are on version 1.x, which is retired. Install the current version; see “Coming from version 1.x” in the [installation guide](installation.md). |
| A helper fails with “No such file or directory” for Python | Run `sh installer/install.sh repair`. Until then Blog Studio can use any Python 3.11 or later. |
| A blog shows an old guidance value, or reviews turned stale after “use the current guidance” | Each blog keeps the version it was started with. Adopting the installed version is your choice and marks earlier reviews stale, because they were judged under the earlier guidance. Rerun the checks you need. |

Your blogs, voices and sources live in the workspace you chose, by default
`.blog-studio` in your writing project. No setup problem requires deleting them.

## Team Hub

- **Team Hub commands fail at once:** a Hub needs Git and a signed-in GitHub CLI.
  Run `gh auth status`; sign in with `gh auth login` using the account that has
  access to your team's Hub repository. Installing Blog Studio does not need
  either tool.
- **Private Hub unavailable:** confirm that your account can open the Hub
  repository in a browser. Membership is managed by your team on GitHub.
- **Queued or pending review:** your work is saved on this computer. Retry sync
  when access returns, or review the contribution pull request. Teammates see
  the change after it reaches the Hub's main branch.
- **Competing blog or rule revisions:** read each version and choose; Blog
  Studio does not overwrite either history.
- **Unshared local edits block resume:** save and share those edits first, or
  use a separate workspace.
- **A teammate uses an older Blog Studio:** ask them to install the current
  version before contributing, so their copy understands the Hub's layout.
