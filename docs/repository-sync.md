# Sync the source repositories

From the Marketing Studio checkout, create your local config once, edit it, then sync:

```sh
cp sync.cfg.sample sync.cfg
bash sync.sh
```

`sync.cfg` is ignored by Git. The tracked `sync.cfg.sample` documents the format:

```ini
[sync]
directory = ~/Projects
discover_harness = true

[repositories]
marketing-studio = https://github.com/dbbaskette/marketing-studio.git
harness-research-skill = https://github.com/dbbaskette/harness-research-skill.git
harness-slides-skill = https://github.com/dbbaskette/harness-slides-skill.git
tanzu-brand = https://github.com/dbbaskette/tanzu-brand.git
```

Change `directory` to choose the destination on that host. `~` expands to the
current user's home; a relative directory is resolved against the config file's
folder. Each key under `[repositories]` is a folder name under that directory.
Add, remove, or change entries to control which checkouts are synced. Git URLs
are used when cloning missing repositories. Existing checkouts pull their current
branch from its configured upstream; changing a URL here does not rewrite Git
remotes. Use URLs without embedded passwords or tokens.

With the config above, all four checkouts live here, including Marketing Studio:

```text
~/Projects/
  marketing-studio/
  harness-research-skill/
  harness-slides-skill/
  tanzu-brand/
```

The configured destination applies even when `sync.sh` is launched from a checkout
elsewhere. Missing destination directories and checkouts are created during sync.
With `discover_harness = true`, other existing `harness-*` Git checkouts in the
same destination directory are included. Set it to `false` to sync only the list.
The studios under `marketing-studio/studios/` update with Marketing Studio; they
do not need separate repositories. Git and an existing Python 3.11+ are required;
installed private Python or an existing uv-managed interpreter can be reused.

Each repository's current branch pulls from its configured upstream using
`--ff-only`, without rebase or automatic stashing. Dirty worktrees (including
untracked files), detached HEADs, branches without upstreams, and unrelated
folders are preserved and flagged for attention. Diverged branches fail safely;
local commits are kept. Branches ahead of their upstream are reported as `AHEAD`
so unpublished commits stay visible. A failed repository does not stop the others.
The command prints Git commands, streams pull/clone output, reports exit status,
and ends with a per-repository summary. Exit code 1 means at least one repository
needs attention. Network commands time out after 180 seconds by default; they do
not wait for interactive authentication. Set up your own Git/SSH credentials first.

```sh
bash sync.sh --dry-run                 # Inspect only; no clone, fetch, pull, or folder creation
bash sync.sh --no-clone                # Only update checkouts that already exist
bash sync.sh --timeout 300             # Allow five minutes per Git command
bash sync.sh --config /path/to/sync.cfg # Use a different config explicitly
```

Config is data, never executed as a shell script. Invalid or explicitly missing
files stop sync before any repository update. If `sync.cfg` is absent, the previous
behavior remains available: discover `studio-package.local.json` (or its legacy
filename) beside `sync.sh`, otherwise use the default component repositories.
That fallback places components beside the launching Marketing Studio checkout.
Legacy packaging JSON also remains accepted by `--config`. Packaging `ref` pins
are left alone: sync updates source branches, while packaging continues to use
the configured release/ref. No installer, dependency update, assistant, or
provider job runs as part of sync.
