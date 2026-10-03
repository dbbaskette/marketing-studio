# What changed and undo

```text
... changes --id <id> --kind draft
... changes --id <id> --against hub
... changes --id <id> --kind draft --revision <listed-history-file>
... changes --id <id> --google-file <returned-markdown> --observation <observation-json>
```

Default comparison is the last local text checkpoint. Results identify the baseline,
changed sections with before/after excerpts, and the available last 30 revisions.
Summarize these facts; inspect full referenced artifacts when excerpts are truncated.
For shared changes, refresh the Hub then use `--against hub`; competing heads
remain explicit and do not select a winner. Never imply a live Google comparison from local history. For latest Google changes,
obtain fresh accepted text and a validated observation via the existing return flow,
then compare both local and Google against the transfer baseline. Explain both-changed
states before choosing a resolution. Comments/suggestions stay separate.

Formatting evidence compares captured native fingerprints where available; absent
or incomparable snapshots are unknown. Native fingerprints include text, so a
changed fingerprint with changed text does not alone prove a formatting edit.

For “Undo that edit”, select the last saved text revision before the just-completed
operation. `before_operation` labels support “before proofreading”; ambiguous
operations or multiple candidates require a focused choice. Legacy unlabeled
history needs content inspection rather than invented operation names.

```text
... article restore --id <id> --revision <listed-history-file>
... article restore --id <id> --revision <same-file> --expected <preview-token> --apply
```

Preview is read-only and returns the exact content/state guard. When the intended
revision is clear, the user's restore request authorizes preview then apply; no
extra approval loop. Apply refuses changed inputs or unresolved Hub conflicts.
It restores draft/outline text as a new revision, retaining the current sources,
voice, rules and guidance pins. It does not restore the immutable original or
Google layout. Explain this scope if the user asks for a complete historical
checkpoint instead. Affected reviews become stale and normal Hub save semantics
apply. No Git reset, forced push, or automatic Google write. Sending the restored
text to Google requires a separate requested transfer and fresh revision checks.
