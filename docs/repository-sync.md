# Sync the source repositories

From the Marketing Studio checkout, run:

```sh
bash sync.sh
```

The command updates Marketing Studio and its components in sibling directories:

```text
~/Projects/
  marketing-studio/
  harness-research-skill/
  harness-slides-skill/
  tanzu-brand/
```

On another computer, clone Marketing Studio into your preferred projects directory,
then run its `sync.sh`. Missing component checkouts are cloned next to Marketing
Studio. Existing sibling `harness-*` Git checkouts are included too. The studios
under `marketing-studio/studios/` update with Marketing Studio; they do not need
separate repositories. Git and an existing Python 3.11+ are required; installed
private Python or an existing uv-managed interpreter can be reused.

Each repository's current branch pulls from its configured upstream using
`--ff-only`, without rebase or automatic stashing. Dirty worktrees (including
untracked files), detached HEADs, branches without upstreams, and unrelated
folders are preserved and flagged for attention. Diverged branches fail safely;
local commits are kept. Branches ahead of their upstream are reported as `AHEAD`
so unpublished commits stay visible. A failed repository does not stop the others. The command
prints the Git commands, streams pull/clone output, reports exit status, and ends
with a per-repository summary. Exit code 1 means at least one repository needs
attention. Network commands time out after 180 seconds by default; they do not
wait for interactive authentication. Set up your own Git/SSH credentials first.

```sh
bash sync.sh --dry-run       # Inspect only; no clone, fetch, or pull
bash sync.sh --no-clone      # Only update checkouts that already exist
bash sync.sh --timeout 300   # Allow five minutes per Git command
```

The command discovers `studio-package.local.json` (or its legacy filename) beside
`sync.sh`. Use `--config /path/to/sources.json` to select another packaging source
config. Git URLs determine the remote and sibling folder name. Local paths
supply their final folder name, allowing a config from another computer to keep
the same sibling layout. A missing custom local folder needs a Git URL in the
config before it can be cloned; the command does not guess its repository.
Packaging `ref` pins are left alone: sync updates source branches, while packaging
continues to use the configured release/ref. No installer, dependency update,
assistant, or provider job runs as part of sync.
