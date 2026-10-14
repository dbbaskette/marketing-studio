# Install Blog Studio

Blog Studio is a skill for the Codex or Claude Code app or CLI on your computer.
Setup copies the whole skill, its instructions and helper scripts together, into
a folder that setup manages. Nothing is downloaded while you write. To get a
newer version, download or pull the update and run setup again.

## Before you start

- **Codex or Claude Code**, installed on this computer and signed in.
- **Python 3.11 or later.** macOS does not include one. If setup reports that it
  is missing, install it from [python.org](https://www.python.org/downloads/macos/)
  and run setup again. Setup finds Python by itself, including Homebrew and
  python.org installations.
- **An installer download or repository clone.** Get the ZIP from the
  [latest release](https://github.com/dbbaskette/blog-studio/releases/latest) or
  your team administrator, or clone the public repository using Git.

Git is needed for the clone option or a Team Hub; a ZIP install and local writing
can work without it. You do not need the GitHub CLI, Node, a Google account or a
model API key to install or to write. A Team Hub also needs the GitHub CLI.

## Install

Choose either method. Both use the same installer and managed skill locations.

### Clone and run

With Git installed, open Terminal and run:

```sh
git clone https://github.com/dbbaskette/blog-studio.git
cd blog-studio
sh installer/install.sh
```

Cloning downloads the current code from the repository. The ZIP option below
installs the packaged release. You do not need a GitHub account to download
either one.

### Download the ZIP

1. Open the [latest release](https://github.com/dbbaskette/blog-studio/releases/latest)
   and download `blog-studio-installer.zip`.
2. Expand the ZIP. Keep the resulting `blog-studio-setup` folder together; the
   installer copies the skill from the `skills` folder beside it.
3. Open Terminal, change into `blog-studio-setup`, and run:

   ```sh
   sh installer/install.sh
   ```

   You can instead double-click `installer/Install Blog Studio.command` in
   Finder; it runs the same setup. macOS may refuse to open that launcher
   because it is an unsigned download. The Terminal command above normally
   still works, so use it rather than changing security settings.

### Finish setup

1. Choose **Codex**, **Claude Code** or **Both**, check the locations shown, and
   confirm.
2. Open your tool in a folder for your writing, start a **new** session, and invoke
   the skill: `$blog-studio` in Codex, `/blog-studio` in Claude Code. Try: “Help me
   build an outline from my notes. Stop at the outline.”

Setup needs no `sudo` and no network. It verifies every copied file, runs the
helpers once in a throwaway folder, and only then switches the skill on. Finding
the skill inside your tool is the one thing setup cannot check for you, which is
why the final step asks for a new session.

To install without questions, for example from a script or when an assistant
runs setup for you:

```sh
sh installer/install.sh install --target both --yes
```

The script also works from any folder with a quoted path:

```sh
sh "/path with spaces/blog-studio-setup/installer/install.sh" check
```

If you want to confirm the download is intact, the release also carries
`blog-studio-installer.zip.sha256`. With both files in one folder, run
`shasum -a 256 -c blog-studio-installer.zip.sha256`.

## Open the writing page

After installation, ask your assistant: **“Use Blog Studio. Open the page.”**
Use an existing writing workspace or choose a new one outside the skill folder.
The same page supports the editorial desk and **New blog**. Writing there needs
an installed, signed-in Codex or Claude CLI. The installer brings the runner as
part of the complete skill; no extra Python packages are needed.

See [page and conversation workflows](https://github.com/dbbaskette/blog-studio/blob/main/docs/runner.md).

## What setup puts where

| Location | Purpose |
| --- | --- |
| `~/.agents/skills/blog-studio` | Link that Codex discovers |
| `~/.claude/skills/blog-studio` | Link that Claude Code discovers; follows `CLAUDE_CONFIG_DIR` |
| `~/.local/share/blog-studio/versions/` | Verified copies of each installed version |
| `~/.local/share/blog-studio/current` | Link to the version in use; both tools share it |
| `~/.local/share/blog-studio/backups/` | Skill folders that setup moved aside with your consent |
| `<writing-project>/.blog-studio/` | Your workspace: sources, voices, blogs and reviews |

If a Blog Studio folder that setup did not create already sits at one of the
skill locations, or an older copy sits in `~/.codex/skills/blog-studio`, setup
asks before moving it to the backups folder. Backups are kept outside the skill
locations on purpose, because a copy left there would show up as a second Blog
Studio. With `--yes`, add `--replace` to give that consent in advance.

Your writing is never inside the installed skill, so installing, updating and
removing Blog Studio do not touch it.

## Update

For a repository clone, open Terminal in your `blog-studio` folder and run:

```sh
git pull --ff-only
sh installer/install.sh
```

For a ZIP install, download the installer ZIP from the newest release and run
setup again.

Both methods update the tools you chose the first time, keep the previous version
for rollback, and leave your writing alone. If only one tool is set up, setup asks
once whether to add the other. Open a new session afterwards.

Each blog records the Blog Studio version it was started with, so its completed
reviews stay meaningful after an update. To move a blog to the installed
version, say “Use the current guidance for this blog.” Its earlier reviews are
then marked stale so you can rerun the ones you need.

### Coming from version 1.x

Version 1.x fetched its writing instructions from the repository each time you
started a blog. That design is retired. A 1.x installation now answers a new
blog with “This guidance needs a newer local Blog Studio runtime. Run the
installer update.” Install the current version as described above; setup
upgrades the existing installation in place.

- Blogs you started in 1.x open and save as before. Their recorded guidance
  shows the earlier value until you ask to use the current guidance.
- You no longer need access to the Blog Studio repository, or a GitHub sign-in,
  to write. A Team Hub still uses your own GitHub access to the Hub repository.
- Each workspace has a `task-context` folder left by 1.x. Version 2 does not
  read it. You can delete it once you are sure you will not roll back to 1.x.

## Check, repair, roll back or remove

Run these from your current `blog-studio` clone or expanded `blog-studio-setup`
folder. Both launchers accept the same words.

```sh
sh installer/install.sh check
sh installer/install.sh repair
sh installer/install.sh rollback
sh installer/install.sh uninstall
```

- **check** changes nothing. It reports the installed version, whether every
  file still matches what was installed, whether the Python that runs the
  helpers still exists, and where each tool's link points. Add `--json` for
  details to share when asking for help.
- **repair** is the same as running setup again. It replaces damaged files with
  a clean copy, records a working Python when the earlier one was removed or
  upgraded away, and finishes a setup that was interrupted. A damaged copy is
  kept beside the new one for diagnosis.
- **rollback** switches back to the version you had before the last update,
  after verifying it. Run it again to return. Rolling back to 1.x restores a
  version that can continue existing blogs but cannot start new ones.
- **uninstall** removes the links from your tools. It keeps your writing, Team
  Hubs, backups and the installed versions. To free the space, delete
  `~/.local/share/blog-studio/versions` afterwards; leave the rest of that
  folder if you use a Team Hub.

Without `--target`, these commands act on the tools chosen at installation, so
repairing a Codex-only setup does not add Claude Code.

| Option | Effect |
| --- | --- |
| `--target codex`, `claude` or `both` | Choose tools explicitly; also adds a tool to an existing installation |
| `--yes` | Do not ask for confirmation |
| `--replace` | Consent to moving an existing unmanaged skill folder to backups |
| `--dry-run` | Show what would change and verify the download; change nothing |
| `--json` | Print structured results |
| `--home`, `--root` | Use another home or managed folder; meant for tests |
| `--offline` | Accepted for older instructions; setup never uses the network |

## Optional: Team Hub

A Team Hub shares blogs, sources and team rules through a private GitHub
repository that your team owns. It needs Git and a signed-in GitHub CLI
(`gh auth login`) with access to that repository. Installation does not set
either up and does not create or join a Hub; ask Blog Studio to “create” or
“join” one. See the
[Team Hub guide](https://github.com/dbbaskette/blog-studio/blob/main/docs/team-hub.md).

## Optional: Google Docs

Blog Studio can work through your tool's own Google Drive connection. If you
prefer the Google Cloud CLI, the installer folder includes a helper:

```sh
sh installer/google-setup.sh --install-cli                # uses Homebrew you already have
sh installer/google-setup.sh --login you@example.com      # opens Google sign-in for that account
sh installer/google-setup.sh --check you@example.com      # read-only access check
```

Google asks for the access every `gcloud` sign-in requests plus full Google
Drive access. Naming the account adds it without changing the account `gcloud`
already uses; add `--activate` to switch. Sign-in creates no Cloud project,
OAuth client or billing setup. See the
[Google Docs guide](https://github.com/dbbaskette/blog-studio/blob/main/docs/google-docs.md).

## Platforms

Setup is built and tested for macOS and Linux. It relies on symbolic links and a
POSIX shell, so Windows is not supported. Claude Cowork and cloud-hosted
sessions are outside what this installer sets up.

If something does not work, see [setup help](troubleshooting.md).
