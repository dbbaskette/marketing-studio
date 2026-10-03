# Editorial board

Run `<runtime>/studio.py --root <workspace> editorial board`. It merges local
blogs with the cached selected Hub graph, reads metadata only, and supports
`--query`, `--stage`, `--owner`, `--limit` (1–50), and `--offset`. Refresh the Hub
only when requested; cached rows cannot establish remote freshness.

Owner is an explicit workflow responsibility, distinct from author and last
editor. Keep Unassigned when unknown. Record a requested decision using
`editorial schedule --id <id> --file <json>` with owner, ISO due date, stage
(idea/draft/review/ready/published), and optional publication_url. Ready requires
a saved draft and an explicit decision. Published requires an actual URL; no
publication occurs. Draft changes invalidate the readiness decision.

For shared-only work, use existing Hub checkout to resume the selected article;
never overwrite unshared edits or choose a competing head silently. Queued and
pending-review work may be visible locally but is not remote main. Sync creates
`editorial/README.md` and links it from the private Hub homepage, with existing
manual-edit protection and immutable history.
