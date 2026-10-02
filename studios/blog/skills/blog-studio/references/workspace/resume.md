# Discover and resume

Use the [workspace](../workspace.md) command prefix.

```text
... init
... list articles
... list profiles
... article show --id <id>
... profile show --id <profile-id> --revision <pinned-revision>
```

For a pinned voice, read only its returned guide/rules.

Inspect metadata first; ask only if several matching articles require a choice.
Read the saved brief, current artifact, interview answer, or decision only when
needed for the next step. Reuse the pending question instead of repeating intake.
Stay within the selected project.

Return a short checkpoint: article/title, stage → next step, stop point, selected
voice/guidance revisions, material gaps, and stale/unavailable reviews. Mention
sync status when present; do not paste full JSON or saved source bodies.

With the bootstrap, reopen the saved guidance task/runtime using
`sync_guidance.py resume --workspace <root> --task <saved-task>`.
A missing runtime is a limitation, not recovered state. Shared checkout,
missing local task IDs, or deliberate guidance changes use [pins](pins.md)
and the [hub router](../hub/workflow.md). Keep current dependencies pinned until
a requested refresh. Verify the selected artifact reopens before claiming resume.
