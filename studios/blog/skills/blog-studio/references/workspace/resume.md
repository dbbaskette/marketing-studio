# Discover and resume

Use the [workspace](../workspace.md) command prefix.

```text
... home --query <title-or-id> --limit 10 --offset 0
... list profiles
... article show --id <id>
... profile show --id <profile-id> --revision <pinned-revision>
```

For a pinned voice, read only its returned guide/rules.

For “My blogs,” use `home` without a query. Show title, stage, last activity, and
next step as a short list; show the workspace and whether a hub is selected. Page
results when requested. An empty list offers a new start; do not scan unrelated
folders. For “continue <name>,” search with `--query`, then inspect the matching
article. Use an exact ID when titles overlap; ask only if the choice is ambiguous.
`home` also works before initialization and never creates a workspace.
Read the saved brief, current artifact, interview answer, or decision only when
needed for the next step. Reuse the pending question instead of repeating intake.
Stay within the selected project. Apply only active `memory` preferences; history
and forgotten entries are not current guidance. Inspect [context](context.md) when
the author asks what is remembered or wants to correct/remove it.

Select the resumed article with `select --id <id>` and show the
[status card](status.md), with one relevant next step. Keep technical pins in
details unless requested; preserve them in the saved task.

With the bootstrap, reopen the saved guidance task/runtime using
`sync_guidance.py resume --workspace <root> --task <saved-task>`.
A missing runtime is a limitation, not recovered state. Shared checkout,
missing local task IDs, or deliberate guidance changes use [pins](pins.md)
and the [hub router](../hub/workflow.md). Keep current dependencies pinned until
a requested refresh. Verify the selected artifact reopens before claiming resume.
