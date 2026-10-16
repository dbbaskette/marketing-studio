# Guided installation

Download and unpack the release, then open
`installer/Install Marketing Studio.command` on macOS, or run
`bash installer/install.sh` on Linux. The shell entry point works before Python
is installed. It offers missing assistant CLIs and shared tools, checks system
prerequisites, provisions agreed prerequisites, then calls the suite installer.

Compatible existing tools are reused. Homebrew is used when available; on macOS
its official installer is offered if missing. Linux also supports existing
`apt-get` or `dnf` repositories providing Python 3.11+ and a suitable Node release.
The shared tools need Node 20+; installing Claude Code through npm needs Node 22+.
Assistant packages go under `~/.local`, without `sudo npm`. Sign-in is a separate
user action; setup never starts a provider job.

```sh
bash installer/install.sh --studios blog --target codex
bash installer/install.sh --studios presentation training --target claude
bash installer/install.sh --prerequisites skip --companions skip --yes
```

`--yes` agrees to the selected installs without prompts. `--assistants skip`
leaves assistant CLIs untouched. `--prerequisites skip` disables all package-manager
and assistant provisioning; `--companions skip` also disables companion fetches.
Alternate `--home` installs, `--dry-run`, help, rollback, uninstall and check never
provision host prerequisites. Older Linux repositories that cannot supply the
required versions receive an actionable error; no third-party package repository
is silently added.

The Python installer stages content-addressed versions and uses each studio's
native installer. It snapshots managed launchers and pointers before changing
them. Workspaces and preferences are preserved. Updating a running studio is
refused. Rollback restores the recorded previous pointers; uninstall keeps the
independent studios and all content.

Upstream installation references:
[Homebrew](https://docs.brew.sh/Installation),
[Codex CLI](https://learn.chatgpt.com/docs/codex/cli), and
[Claude Code npm setup](https://code.claude.com/docs/en/setup#install-with-npm).
