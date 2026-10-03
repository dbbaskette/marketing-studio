# Inspectable claim evidence

Use selected factual-reference roles and pinned revisions, never inspiration,
voice samples, or biography as factual proof. Retrieve only needed passages with
existing `passages`. Choose important claims and apply the existing fact-check
module to judge support; the helper verifies spans, not semantic truth.

Save `editorial evidence --id <id> --file <json>` with a JSON list:
`[{"claim":"exact manuscript text","start":0,"status":"supported",
"reason":"bounded assessment","citations":[{"source":0,"quote":"exact source passage","start":0}]}]`.
Source positions refer to selected reference sources in attachment order. States:
supported, contradicted, insufficient, not-checked. Supported/contradicted require
exact pinned quotations. Absence of evidence does not establish falsity.

The helper stores manuscript and source hashes, citation offsets, names and
portable origins in `derived/evidence.json`; current/stale status appears in
`editorial assets --id <id>`. Report the selected claim scope and remaining gaps,
without a blanket accuracy score. A source revision stays pinned until explicitly
changed; reverify historical product claims against current primary sources.
