# Shared writing with Team Hub

Team Hub keeps the team's read/write work in a private GitHub repository,
separate from Blog Studio's skill repository. Each member has a managed local
clone. Blogs, outlines, sources, voices, interviews, decisions, reviews, reusable
notes, and team rules travel together. The workflow stays in your harness.

## Start in chat

> Use Blog Studio to create a Team Hub named Marketing Writing at my-org/marketing-writing. Use it for this writing project.

The skill obtains missing repository/workspace details, creates the private
remote and validated local clone, and selects it. Creation uses your signed-in
GitHub account; it does not invite members or change repository permissions.

> Join our Team Hub at https://github.com/my-org/marketing-writing and use it for this project.

Members need existing access to that private repo. Join reports whether writing
is available. All members also need access to the separate private Blog Studio
repository for maintained skill guidance.

> Find our draft about customer onboarding and help me finish its outline.

The skill refreshes the hub, finds the chosen article, and restores its saved
checkpoint and pinned dependencies. A clean imported copy can move to the newer
shared version; unshared local edits are preserved and block replacement.

> Remember this for our launch project: use sentence-case headings.

The skill saves the selected rule with its scope. Team defaults are available
at task entry; explicit project/author/article selections take precedence.
Competing rules require a choice. An ongoing article retains selected revisions
until deliberately refreshed.

## What gets shared

Once a writing workspace selects a hub, normal Blog Studio saves synchronize
that changed item and its dependencies. An article includes its original,
outline/draft history, interview and decisions, derived copy, source roles,
voice revision, guidance commit, selected context, and review state. Original
uploads retain their bytes; automatic sharing excludes machine-specific paths,
runtime caches, and incidental configuration files.

Joining does not upload prior work. Ask to share specific existing articles,
sources, or profiles. Their actual selected dependencies follow automatically.
A workspace without a hub keeps the existing local-only behavior.

## Where to find your work

Open `blogs/README.md`, then the blog's author/title folder. Each blog contains
its current `README.md`, `draft.md`, immutable `original.md`, saved outlines,
`reviews/` with readable edits and their coverage/status, `sources/` with only
selected pinned evidence, `companions/`, and `history/` with earlier drafts and
Google import attachments. Missing artifacts are omitted; empty review/source
indexes explain what has not been saved. Competing drafts stay separate in the
history until you choose a resolution.

`memory/README.md` contains reusable rules, voices, context, notes, and decisions.
Article-specific drafts and reviews stay with their blog. Synchronization data
lives in `.blog-studio/items/`; it is not the folder authors need to browse.

Runtime **1.13.0** reads existing hubs and upgrades them on an authorized save or
sync. The upgrade preserves every original record, attachment, revision ID, and
pin byte for byte, and retains earlier Git commits. Other contributors need the
1.13.0 installer before writing to the upgraded hub. Joining or refreshing alone
does not migrate the repository. Generated files remain managed by Blog Studio;
manual edits are preserved and block regeneration until reconciled.

## Saves and connection problems

| Status | What it means |
| --- | --- |
| Shared / synchronized | Verified on shared main; other members receive it at their next refresh |
| Queued | Saved locally; retry when the network or contribution access returns |
| Pending review | A contribution PR is waiting for repository review/merge |
| Conflicted | Multiple versions retained; choose a resolution before resuming the shared head |
| Local saved, not shared | Local save survived an adapter error; inspect the message and retry selected import |

Offline saves keep durable operation IDs, so retries do not duplicate work.
Two members' independent additions combine. Two edits from the same article
baseline remain separate revisions until an explicit resolution includes both
parents. No forced pushes or silent manuscript merging occur.

Protected main uses a contribution branch and PR. The helper does not merge
that PR or change branch rules. An unprotected hub can sync directly. A hub
created with review mode always uses a PR.

## Setup and helper examples

Update to the trusted **1.13.0 installer runtime** to use Team Hub. Run the new
bundle through the existing setup/update flow. Git and authenticated GitHub CLI
are required for the current provider. Credentials remain in provider storage.
Use the interpreter in the managed runtime configuration when necessary.

```text
python3 <runtime>/hub.py --workspace <absolute-workspace> create --repo my-org/marketing-writing --name "Marketing Writing"
python3 <runtime>/hub.py --workspace <absolute-workspace> join --repo https://github.com/my-org/marketing-writing
python3 <runtime>/hub.py --workspace <absolute-workspace> status
python3 <runtime>/hub.py --workspace <absolute-workspace> find --kind article --query onboarding
python3 <runtime>/hub.py --workspace <absolute-workspace> checkout-workspace --article <shared-id>
python3 <runtime>/hub.py --workspace <absolute-workspace> import-workspace --article <local-id>
python3 <runtime>/hub.py --workspace <absolute-workspace> sync
python3 <runtime>/hub.py --workspace <absolute-workspace> leave
```

Default registry/clones live under `~/.local/share/blog-studio/hubs/`; the writing
workspace remains separate. `--registry` chooses another absolute registry,
`--destination` chooses a new clone container, and `list` shows joined hubs.
Leaving a project retains its clone, queue, and all shared history.

## Progressive disclosure and Google Docs

The parent loads one [team router](../skills/blog-studio/references/hub/workflow.md)
only when team work is relevant. Setup, memory, and sync instructions load when
needed. Search returns a short catalog; reads return selected artifact paths.
Downloading a repository does not load all its content into model context.
See measured estimates in the [roadmap](progressive-disclosure-roadmap.md).

Google Doc identities and transfer baselines can be retained as portable data.
Native source intake and draft handoff/return remain the
[next Google Docs phase](google-docs-roadmap.md); Team Hub does not perform those
provider operations yet.

## Verification boundary

**Verification:** the full suite contains 87 tests, covering the existing local
workflow, guidance refresh/pins, installer/rollback, extracted bundle, and Team
Hub. Package integrity, both skill entries, and launcher syntax are checked too.

Automated tests use disposable member homes and local repositories with a fake
GitHub provider. They cover lifecycle recovery, offline queues, races, response
loss, protected-branch outcomes, conflicts, scopes, and cross-machine handoffs.
A real GitHub team pilot, clean-Mac setup, and live Codex/Claude discovery remain
separate verification steps. No live Team Hub was created during implementation.
See the [schema](team-hub-schema.md) and [design record](team-hub-design.md).

## Readable GitHub library

Open the hub’s GitHub homepage or `blogs/README.md` to browse title, author, stage,
and last update. Article folders render the current manuscript, saved outline,
selected-context links, and readable revision history. Conflicts show competing
versions until explicitly resolved; retired articles disappear from the current
library while their canonical history remains.

Ask “Set this blog’s author to Alex Rivera,” “Rename this blog to Better handoffs,”
or “Sync our hub so we can browse the blogs in GitHub.” Author/title metadata
changes do not rewrite the draft. Missing author metadata falls back to the pinned
voice’s name, then Unassigned; the uploader/last editor is not presumed to be author.
A title or author rename can change its folder URL, so use canonical revision links
when a permanent reference is needed.

This is part of candidate runtime **1.3.0**. Upgrade contributing clients through
the trusted installer before migrating a hub. New hubs include an empty library;
existing hubs upgrade with their next successful save or explicit sync. Joining or
refreshing alone makes no remote changes. In review mode, generated files appear
on the contribution branch first. Read-only/offline clients retain queued work.

Edit through Blog Studio. If a generated page or its homepage section is edited in
GitHub, sync stops before replacing it. Preserve the edit, import desired changes
through the article workflow, and restore the generated file from its prior Git
version before retrying. Custom homepage text outside the marked library block is
preserved. No Git history is rewritten and unrelated memory is not copied into the
blog pages.
