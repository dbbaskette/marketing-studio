# Create or join a Team Hub

Use the member's existing authenticated GitHub account. The initial provider
requires Git plus authenticated GitHub CLI (`gh`) for creation, identity,
permissions, and PR diagnostics. Follow installer setup help if unavailable;
do not switch accounts or grant membership. Team members already need access
to the private repository and contribution rights if they will write.

For create, obtain a concrete GitHub owner/repository and friendly name. The
create request authorizes that specific private repository and its seed; ask
only for missing targets. The standard Hub folder is `~/blogs/<repository-name>/`: a normal Git checkout
with readable shared files and history. Local drafts, selection, snapshots and
queued work live under its ignored `.blog-studio/` directory. Report this folder
and use its `.blog-studio/` as the writing workspace. An explicit
`--destination <absolute-new-directory>` overrides the Hub folder. With no
workspace argument, create/join initializes and selects the default workspace.
An isolated custom registry defaults to `<registry>/workspaces/<repository-name>/`.
`--registry <absolute-directory>` supports separate managed registries.

```text
python3 <runtime>/hub.py create --repo <owner/repository> --name <friendly-name>
python3 <runtime>/hub.py join --repo <GitHub-HTTPS-URL>
python3 <runtime>/hub.py list
python3 <runtime>/hub.py --hub <hub-id> --workspace <workspace> select
python3 <runtime>/hub.py --workspace <workspace> status
python3 <runtime>/hub.py --workspace <workspace> leave
```

Join validates the private repo, hub schema, UUID, and provider identity before
activation. Existing destinations or unrelated remotes are preserved. Creation
persists its intended UUID first; retry the same owner/name after an uncertain
result. Never invent a replacement name or retry against another repository.

Confirm the observed outcome: hub identity, local clone, writing workspace,
contribution capability (`write`, `read-only`, `unverified`), and freshness.
Explain that work in this selected workspace shares by default. Local-only
writing remains available in a workspace without a selected hub. Leave removes
only this project's selection, retaining clones, queued work, and remote data.

A hub's `auto` mode observes main protection and uses a contribution PR when
protected. `review` always uses a PR; `direct` still respects observed protection
and never force-pushes. Establish permissions/branch rules outside this workflow;
the helper does not invite members, edit rules, or merge its PR automatically.
For a real created contribution PR, attach its returned URL with the host's
pull-request artifact tool when available.

Existing local work is shared only when named explicitly:

```text
python3 <runtime>/hub.py --workspace <workspace> import-workspace --article <local-article-id>
```

Repeat `--article`, `--source`, or `--profile` for selected items. Selected article
dependencies follow automatically. Do not upload unrelated projects or hidden
configuration. The automatic adapter shares recognized writing artifacts only.

## Existing Hubs

A legacy bare clone remains usable until explicitly migrated. For “Move our Hub
to the standard folder,” inspect status and the destination, then run:

```text
python3 <runtime>/hub.py --hub <hub-id> migrate --destination <absolute-hub-folder>
```

Omit destination to use the standard folder. Migration uses local Git objects,
preserves queued and pending-review work, and retains the old clone as a backup.
An existing folder is accepted only when it contains solely `.blog-studio/`
selected for this same Hub; its drafts are preserved. Other occupied destinations
are refused. Open the reported workspace after migration. Existing explicit
workspace selections continue to resolve through the registry. Sync refuses to
overwrite edits or different commits in the normal checkout; preserve those
changes before retrying. Shared revisions still go through Blog Studio saves.
