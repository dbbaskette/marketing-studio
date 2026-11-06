# Training Studio: readable output and truthful progress

Authorized by the request to review the process and implement another round of
improvements. Issue #387 covers scheduling; issue #388 covers progress;
issue #391 covers the final Golden Gate v2 UI audit.

## Findings and implementation order

1. Every level's plan precedes the first guide. A deck and its approval then block
   later guides and all practice even though these materials do not consume it.
   New outline-first runs pin a readable-first order: each level's plan, guide and
   brief; then practice and Yoodli; then decks. Earlier objectives remain available
   to higher levels. Selected inputs and all approvals remain required.
2. The desk marks every missing material as being written while any step runs.
   Show the active material separately from queued materials and explain the queue.
   A creator-approved research phase also hid the new material activity. Treat it
   as finished for scheduling/progress, keep its uncertainty notice, and collapse
   the saved decision details once material work starts. Queued updates remain
   downloadable and never unlock level readiness.
3. Parallel source checking and a durable concurrent material scheduler remain
   larger follow-ups. This increment changes priority, not concurrency or spending.
4. The phone desk repeated the active step and expanded worker metadata in a large
   progress card. Replace that frame with an integrated progress region, keep the
   latest activity visible, and disclose detailed activity/timing separately.
5. Outline review put several paragraphs of process detail before its first field.
   Keep the approval consequence, source scope and incomplete-outline warnings
   visible. Disclose the research approach, scan notes and limits together.
6. Creation repeated model, timing and concurrency settings in its review summary
   even though Assistant and limits already contains them. Keep the next action,
   selected outputs and spending amount in the summary; use the existing disclosure
   for the detailed settings.

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
| One material worker active | Read progress | Only its artifact says Writing; peers stay Queued | Native standing test |
| Update queued or stopped | Read progress | Queued, with reason; saved draft remains downloadable | Native standing test |
| Training waits for a slot or approval | Read progress | No inactive material says Writing; next queued material is named | Native and browser tests |
| Creator research choices saved | Continue | Material progress and draft counts appear; uncertainty stays marked | Browser journey |
| Queued update has an older saved draft | Read desk | Download remains available; level readiness stays unavailable | Native and page tests |
| Activity or research approach open | Poll | Disclosure and keyboard focus retained | Native browser journeys |
| Incomplete starting outline | Review | Warning remains visible while process details are folded | Outline browser journey |

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

Progress evidence: commit `97462543` passed all 3,207 Training Studio tests and
package validation on disposable macOS 27 / Python 3.13.15 / Node 22.23.2. The final
worker-registry snapshot guard at `83333a09` passed all nine native standing tests
and the actual native browser journey, including concurrent polling and Stop/Resume.
The browser covered 390/1280px, light/dark, reduced motion, saved decision disclosure,
and reload without new jobs. Fifteen shared research/UI checks passed. The test VM
was deleted. No paid provider work or real training state was used.

Golden Gate v2 evidence: 410 Training Studio page tests, 16 shared UI checks and
package validation passed on host macOS / Python 3.13.5. Native browser journeys
covered creation/source picking/save/reopen/discard without starting work;
outline editing, approval and incomplete-scan recovery; reading and Finishing;
settings scrolling/focus return; and progress Stop/Resume. Populated 320/390/1280px
layouts were checked in light/dark and reduced motion. The progress journey also
checked forced colors and 200% text enlargement. Final disclosure refinements
passed the outline/progress journeys, including focus and open-state retention
on polling and 44px disclosure targets. The 390px scripted progress region stays
under 300px tall; the first outline title field is visible without scrolling.
Screenshots were inspected for the phone desk, outline, creation, reading and
settings, and the dark desktop desk. These are Chromium checks, not VoiceOver,
Safari or OS-preference integration claims. No live provider latency was measured.

An older standalone creation journey assumed the retired one-page form; the
current intake journey was used instead. The unchanged native scheduling and
research runtime reuse the full 3,207-test Tart evidence above.
