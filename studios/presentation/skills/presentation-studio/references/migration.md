# Open unfinished saved work on the desk

Only migrate at the person's explicit request. Run `studio desk migration-preview --folder PATH` first. Show retained materials, incomplete work, blockers and consequences; keep its token hidden. Preview and Cancel change nothing.

Saved schemas 1–3 need a usable outline; Selected changes needs its inventory and original deck. Sources and pinned research must verify. Brief-only, unreadable or unsupported work keeps its saved flow. Worker markers block migration: use existing saved-flow Stop/recovery when appropriate. Recovery may discard uncommitted work. Never delete markers or invent completion.

After confirmation, run `studio desk migrate --folder PATH --expected TOKEN` with the exact token. Changed inputs, workers, owner or workspace refuse. It opens the same folder in conversation with scope `['part']`: existing slide parts only. Broader work needs explicit `desk scope`. Nothing is approved, drawn, researched, installed or delivered.

Original `run.json`, materials, History, pins, earlier real decisions and Google records stay intact. Effective state lives in `desk/migration.json`, paired with immutable `desk/migration-origin.json`. A local pending transaction blocks execution until explicit migration retry safely finishes or rolls back metadata. Never edit these files. A prior stopped/failed runner status remains visible in History; conversation editing does not resume that runner.

Migration raises the workspace requirement to **4.8.1**, preserving higher floors. Close older instances; configured older runtimes may ignore the requirement. Setup/join enforce it. Any installation or update is explicit.

Shared migration requires retained deck files and the workspace record to match HEAD and index, including tracked ignored files. Commit intended changes through the saved flow or Git, then preview again. Migration commits only desk records and the floor. Private ignored inputs stay local; local dirty work is supported, not a complete Git backup. Marketing Studio Connect claims effective ownership, preserving originals/receipt; unsupported runtimes refuse.

The page offers **Open on the desk**, preview, Apply/Cancel. Finished decks retain adoption and delivery guards. `studio saved-work` reports original compatibility dependencies and unknown records; local inventory cannot establish other installations' needs.

## The person's final approval

Read `studio desk context --folder PATH --target ready`. Show the actual checked deck, review status and every brand blocker to the person. Only their actual approval permits `studio desk ready --folder PATH --input FILE`:

```json
{"expected_basis":"<current basis>","seen":{"revision":1,"expected":"<current drawing>","blockers_seen":"<current blockers>"},"response":"<the person's actual approval>"}
```

Echo context's complete `seen`; never default the response or silently acknowledge blockers. **Mark ready** uses the same checked decision. Missing dependencies, open design decisions, incomplete drawings, changed inputs, another driver or workers refuse it. Never fabricate earlier runner approvals.

Selected changes uses read-only native compare/inspect against the retained original and patch. An unavailable checker refuses Ready. Older copies may lack historical deck/image hashes. Only the person's explicit acknowledgment permits `seen.historical_proof_ack` to change from false to true. The page requires an unchecked acknowledgment plus their response. Approval binds the current copy, complete previews and checks; it proves no historical byte equality and backfills nothing. Existing hashes remain mandatory.

Ready records only the person's build approval and keeps conversation execution. It starts no job, copy, upload or delivery and needs no invented runtime/research pin. It does not claim Delivered. Later material/input changes require a new approval. Normal runner Deliver remains separate.
