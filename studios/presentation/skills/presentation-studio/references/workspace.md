# The workspace

Presentation Studio keeps decks under the configured `presentations/` folder in a team repository or a local workspace. Shared settings select the workspace. If none is configured, ask where work belongs and use explicit setup; never initialize a different folder implicitly.

## Conversation records

Use `studio desk create/show/context/submit/save/answer/take/scope/handoff` as [the desk contract](desk.md) describes. They use the existing workspace and repository lock. Never write `run.json`, draw files or mark steps/approvals yourself.

A deck lives at `presentations/<deck-id>/`:

| File or folder | Meaning |
| --- | --- |
| run.json, intake.md, README.md | Checked form, saved decisions, ownership and status |
| classify.json / classify.md | Existing-deck inventory or document classification |
| outline.json / outline.md | Checked Harness Slides outline and readable words |
| research/ | Plan, reviewed bundle and evidence |
| brand/ | Pinned contract and brand reading |
| desk/ | Shared History of each slide's words |
| work/ | Local drawings, pictures, checked build state and drawing History |
| sources/ | Local documents and preserved original deck |
| deliver.json | The last actual delivery; prior revisions remain in the run record |

A conversation record keeps `flow: desk`, `execution: conversation`, a finite `conversation_scope` and checked submission dependencies/provenance. Scope and execution changes never alter saved materials or readiness. A material change retains previous decisions as history and holds affected later work for checking; no submission becomes person approval. Original files and Google baselines are preserved.

`work/`, `sources/`, locks and companion caches are never shared. Drawings can be missing on another computer even when their outline and History are present. Conversation context reports prerequisites rather than recovering or fetching them implicitly. JSON intake allows `uploads: {"source-name": "/absolute/local/file"}`; the named file is read only when explicitly supplied. A Google link is preserved as input, never silently fetched: explicitly provide a local export if it has not been imported.

## With a team

Only the current driver may change work. Checked saves, execution transfer and scope changes recheck ownership and active canonical workers under the same process lock as page and synchronization writes. Competing old forms are refused. Share through the existing team commands/settings; never force a push or discard someone else's work.

## Supported saved work

Older gated records and review policies retain their readers and real historical decisions. A delivered gated deck can still use the existing **Open on the desk** adoption; it stays delivered until an actual change. Conversation can then explicitly take that desk without a browser. An unfinished old flow needs the supported saved-work/migration path; do not pretend it is finished, rewrite its format or manufacture gates. `studio saved-work [--folder PATH]` inventories declared local scope read-only; it cannot certify other installations or clones.
