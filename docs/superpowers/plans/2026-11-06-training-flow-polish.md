# Training Studio: readable output and truthful progress

Authorized by the request to review the process and implement another round of
improvements. Issue #387 covers scheduling; a second increment covers progress.

## Findings and implementation order

1. Every level's plan precedes the first guide. A deck and its approval then block
   later guides and all practice even though these materials do not consume it.
   New outline-first runs pin a readable-first order: each level's plan, guide and
   brief; then practice and Yoodli; then decks. Earlier objectives remain available
   to higher levels. Selected inputs and all approvals remain required.
2. The desk marks every missing material as being written while any step runs.
   Show the active material separately from queued materials and explain the queue.
3. Parallel source checking and a durable concurrent material scheduler remain
   larger follow-ups. This increment changes priority, not concurrency or spending.

## State-transition matrix

| State | Event | Result | Verification |
| --- | --- | --- | --- |
| New outline-first run | Create | Versioned readable-first policy saved | Native creation test |
| Research accepted | Next material | First plan, then its selected guide and brief | Pipeline and native integration |
| First level readable | Next level | Later plan receives earlier objectives | Multi-level integration |
| Readable materials complete | Practice selected | Practice precedes slide approval/design | Native integration |
| Slide text waiting | View | Earlier readable materials remain available, not marked ready | Native integration |
| Saved run without pin | Load | Original order preserved | Compatibility test |
| Explicit material update | Survey | Existing scoped update/hold order preserved | Update regression |
| Invalid scheduling pin | Load | Refuse unknown policy | Record validation |

## Verification

Use disposable settings/workspaces, scripted workers and the pinned helper fixture.
Compare dispatch positions with equivalent scope. This proves reduced scheduling
delay; it does not predict provider latency or establish live output quality.
Run the affected tests at the slice boundary and the full Training Studio suite
once in the shared disposable Tart runner. No real training or provider job is used.

Scheduling evidence: application commit `a66dd861` ran all 3,202 Training Studio
tests on disposable macOS 27 / Python 3.13.15 / Node 22.23.2. One legacy fixture
incorrectly retained the new scheduling pin while constructing an older run; the
other 3,201 tests passed. Removing that pin from the legacy fixture passed all 12
outline tests on Python 3.13.5, and package validation passed. Application code
was unchanged by that correction. The disposable VM was deleted.
