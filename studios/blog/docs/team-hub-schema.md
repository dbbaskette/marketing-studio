# Team Hub schema and portable checkpoints

Schema 1 requires runtime 1.1.0 or newer. Hub, item, revision, and operation IDs
are 32 lowercase hexadecimal UUID-style identifiers. Git snapshot IDs are
40–64 lowercase hexadecimal digits. A memory revision ID equals its durable
operation ID; it is distinct from the containing Git snapshot.

```text
hub.json
README.md
memory/items/<item-id>/revisions/<revision-id>/record.json
memory/items/<item-id>/revisions/<revision-id>/BODY.md
memory/items/<item-id>/revisions/<revision-id>/artifacts/<safe-relative-name>
```

The manifest contains schema, hub UUID, friendly name, canonical GitHub
owner/repository, main branch, minimum runtime, and auto/direct/review mode.
Repository identity and privacy are verified through provider metadata.

Every record contains schema, item/revision/operation, kind, title, summary,
status, parent revision IDs, pinned dependencies, scope, tags, actor, creation
time, user data, and an artifact inventory with SHA-256 hashes and text/binary
media. A dependency names item, revision, and kind; optional role/purposes retain
meaning. Parents must exist on the same item, whose kind never changes. Cycles,
missing dependencies, repeated operation IDs, unsafe paths, and unrecorded files
are rejected. A tombstone hides a current item without erasing old revisions.

Kinds are article/source/voice/note/decision/rule/context/review. Scope contains
level (team/project/author/article) and key (empty for team, required otherwise).
Rules/context may use a preference key in data for conflict detection. Scope
and tags govern discovery; they do not change repository access controls.

A portable Blog Studio item stores its core checkpoint under `data.studio`.
Article source/voice references use shared IDs rather than local counters.
Guidance contains trusted repository and commit, never an absolute runtime/cache
path. Imported sources/voices receive revision-specific local projection IDs;
articles retain a stable local projection ID. Local maps, selections, outbox,
read caches, and derived catalogs remain outside the remote tree. Original
uploads are intentional source content; credentials must never be added as
source material or explicit attachments.

Reviews retain result/status and portable input provenance. Local IDs are
translated at checkout; existing stale/failed/unavailable statuses remain so.
Draft/voice/evidence/guidance/context adoption changes relevant freshness.
The article's `google_docs` field, when explicitly provided, is portable data
for Doc identity/URL, tabs, observed revision, transfer hash/direction/time, and
verification result; no provider access is implied by its presence.

Only regular non-executable Git blobs are accepted. UTF-8 text has a 1 MiB limit,
binary attachments 10 MiB, a snapshot 100 MiB total and 20,000 files. Limits
apply before materialization. Remote files are read as data in a bare repository;
no remote checkout, hooks, scripts, configuration, or Git filters execute.
Existing published revision bytes cannot be edited or removed by refresh.

Independent operations use different paths and combine. Multiple revisions
with the same parent yield divergent heads. An explicit complete resolution
with every current head as parent converges that item without deleting either
history. PR mode keeps contributions local/pending until verified on main.
The bounded sync retry count is three; locks serialize local operations.

New providers, compaction, permanent deletion, encrypted per-author visibility,
and scheduled background synchronization are outside schema 1's runtime.
