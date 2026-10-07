# Review records and derived content

Use the [workspace](../workspace.md) prefix.

```text
... article review --id <id> --check <check> --status <status> --file <findings.json>
... article derive --id <id> --name <format-name> --file <copy>
... article show --id <id>
```

Checks: proofread, factual-support, shape, humanization, geo. Save current,
unavailable, or failed; current requires an actual completed check and JSON
`{"findings":[]}` (empty only when nothing was found). Include coverage limits
and source IDs/revisions/passages; for factual work use [evidence selection](../review/evidence.md). Keep coverage/claims when extending partial reviews. No readable evidence makes factual-support unavailable.

Readback computes freshness: draft, voice, guidance or shared-context changes
stale dependent checks; source changes affect factual support/GEO. Not-run,
failed and unavailable remain distinct. Return findings/statuses briefly; never
claim a check ran because a record exists. Replaced reviews retain history.

Derived content saves separately and retains prior versions; never overwrite
the manuscript. For deterministic lint, fact-token comparison, or counts, read
[mechanical checks](checks.md); those helpers do not certify editorial quality.
