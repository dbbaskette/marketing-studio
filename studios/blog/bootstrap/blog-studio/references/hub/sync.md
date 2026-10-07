# Durable sync and competing revisions

```text
python3 <runtime>/hub.py --workspace <workspace> sync
python3 <runtime>/hub.py --workspace <workspace> refresh --offline
python3 <runtime>/hub.py --workspace <workspace> history --item <item-id>
```

| Outcome | Meaning and next step |
| --- | --- |
| shared / synchronized | Operations verified on shared main |
| queued-offline / queued-unavailable | Durable local work; retry sync when access returns |
| queued-read-only | Work retained; contribution rights need the repository administrator |
| queued-contention | Bounded push retries exhausted; retry later with the same queued operations |
| pending-review | Contribution branch/PR exists; teammates receive it after merge to main |
| local-saved-not-shared | Local studio save succeeded but hub serialization/sync failed; inspect the error and retry explicit selected import |

A save revision ID identifies a memory operation; `hub_commit` identifies the
verified Git snapshot. Stable operation IDs deduplicate retries, including an
uncertain push result. Never create another operation just because delivery was
uncertain. Runtime 1.13.0 may relocate immutable records from legacy `memory/items/` to
hidden `.blog-studio/items/` during authorized sync. Every byte and identity must
match; this is not removal of saved work. Queued old-layout operations retain
their payload hashes and IDs while being delivered to the new path.

Never change branch rules, overwrite existing revisions, force-push,
or claim pending work is shared. Attach real contribution PR URLs with the
host artifact tool. The user/repository policy controls review and merge.

Independent records combine. Concurrent changes to one item retain multiple
heads; reads require an explicit revision until resolution. Show the competing
content and preserve both histories. Compose the author's chosen resolution,
then name every current parent:

```text
python3 <runtime>/hub.py --workspace <workspace> resolve --item <item-id> --kind <kind> --title <title> --parent <revision-a> --parent <revision-b> --file <resolved-body> --data-file <resolved-data-json> --dependencies-file <pinned-refs-json> --artifact DRAFT.md=<resolved-draft-path>
```

Resolution is a complete checkpoint. For a Blog Studio article retain/merge its
`data.studio`, original, outline, interview, review provenance, source/voice refs,
and required artifacts. The selected DRAFT.md and BODY.md must agree. Read both
records/artifacts and explicitly choose parents; do not resolve only the body
and discard metadata. Import the resolved head into a clean/new workspace;
preserve the authoring workspace until that round trip is verified.

Removal uses `remove --item ... --kind ... --title ...`, producing a tombstone.
Previous revisions remain in Git and can be read explicitly. This is not a
permanent erasure operation. A stale lock or staging directory after interruption
is retained for diagnosis; verify that no process is running before removing
only the owned lock/temporary stage. Do not delete the outbox or working content.
