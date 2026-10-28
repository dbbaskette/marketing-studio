# Open unfinished saved work on the desk

Only migrate at the person's explicit request. Run `studio desk migration-preview --folder PATH` first. Show retained materials, incomplete work, blockers and consequences; do not display its machine token. Preview and Cancel change nothing and start no jobs.

Eligible saved schemas 1–3 need a usable outline; Selected changes needs its inventory and preserved original deck. Required sources and pinned research must verify. Brief-only, unreadable or unsupported work keeps its saved flow. Any worker marker blocks migration, including after interruption: use existing saved-flow Stop/recovery first when appropriate. That recovery may discard uncommitted work. Never remove markers yourself or invent step completion.

After confirmation, run `studio desk migrate --folder PATH --expected TOKEN` with exactly the preview token. Changed inputs, workers, ownership or workspace refuse it. It opens the same folder with conversation execution and scope `['part']`: existing slide-part edits only. Broader work requires the person's explicit `desk scope` change. Nothing is approved, drawn, researched, installed or delivered.

Original `run.json`, materials, History, pins, earlier real decisions and Google records stay intact. Effective state lives in `desk/migration.json`, paired with immutable `desk/migration-origin.json`. A local pending transaction blocks execution until explicit migration retry safely finishes or rolls back metadata. Never edit these files. A prior stopped/failed runner status remains visible in History; conversation editing does not resume that runner.

Migration raises the existing Presentation Studio workspace requirement to at least **4.8.0**, preserving higher requirements. Use that version or newer and close older running instances before applying. Compatible setup/join paths enforce the requirement; an already configured older runtime may ignore it. No automatic installation or update occurs.

The page offers **Open on the desk**, preview, then Apply or Cancel. Finished saved decks retain their existing adoption and delivery guard. `studio saved-work` still reports original compatibility dependencies and unknown records; local inventory cannot prove that other installations no longer need an older format.

## The person's final approval

Read `studio desk context --folder PATH --target ready`. Show the actual checked deck, review status and every brand blocker to the person. Only their actual approval permits `studio desk ready --folder PATH --input FILE`:

```json
{"expected_basis":"<current basis>","seen":{"revision":1,"expected":"<current drawing>","blockers_seen":"<current blockers>"},"response":"<the person's actual approval>"}
```

Echo the complete `seen` value from context; never supply a default response or silently acknowledge blockers. The page's **Mark ready** action uses the same checked decision. Missing dependencies, open design decisions, incomplete drawings, changed inputs, another driver or workers refuse it. Do not fabricate earlier runner approvals to make conversation materials eligible.

Ready records only the person's build approval and keeps conversation execution. It starts no job, copy, upload or delivery and needs no invented runtime/research pin. It does not claim Delivered. Later material/input changes require a new approval. Normal runner Deliver remains separate.
