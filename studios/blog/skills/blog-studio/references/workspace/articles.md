# Articles and checkpoints

Use the [workspace](../workspace.md) prefix. For a new article first read
[creation](create.md); [pins](pins.md) handles deliberate guidance changes.

```text
... article save --id <id> --kind <brief|original|outline|draft> --file <file>
... article note --id <id> --kind <interview|decision> --text <text>
... article progress --id <id> --stage <stage> --next-step <next> --pending-question <question>
... article show --id <id>
... article author --id <id> --name <author>
... article rename --id <id> --title <title>
```

Save the untouched original before edits in existing-draft mode. Originals
are immutable; brief/outline/draft saves snapshot previous versions in `history/`.
For “undo” or a named earlier version use [guarded recovery](changes.md).
Feedback-only leaves the manuscript intact. Draft edits stale affected reviews.

Keep stage, next step, and pending question accurate at meaningful checkpoints.
Omit the pending-question option when none remains. Saving does not authorize
another stage: outline-only/brief stop before drafting; change `--stop` only when
the author requests a different outcome. The save result includes `saved_artifact.reopened` after a byte-for-byte local
readback. Use that receipt for file-save verification; inspect the prose separately
when assessing content. Give a compact
saved/stage/next-step summary, including sync problems. Keep derived copy separate
through [reviews/derived content](reviews.md).

Author/title changes update library metadata without rewriting the manuscript.
Shared GitHub browsing and migration use the [hub library](../hub/library.md).
