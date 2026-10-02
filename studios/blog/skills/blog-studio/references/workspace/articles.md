# Articles and checkpoints

Use the [workspace](../workspace.md) prefix. For a new article first read
[creation](create.md); [pins](pins.md) handles deliberate guidance changes.

```text
... article save --id <id> --kind <brief|original|outline|draft> --file <file>
... article note --id <id> --kind <interview|decision> --text <text>
... article progress --id <id> --stage <stage> --next-step <next> --pending-question <question>
... article show --id <id>
```

Save the untouched original before edits in existing-draft mode. Originals
are immutable; brief/outline/draft saves snapshot previous versions in `history/`.
Restore by saving a prior version as a new current artifact, retaining history.
Feedback-only leaves the manuscript intact. Draft edits stale affected reviews.

Keep stage, next step, and pending question accurate at meaningful checkpoints.
Omit the pending-question option when none remains. Saving does not authorize
another stage: outline-only/brief stop before drafting; change `--stop` only when
the author requests a different outcome. Read back the artifact and give a compact
saved/stage/next-step summary, including sync problems. Keep derived copy separate
through [reviews/derived content](reviews.md).
