# Bounded parallel research

Status: proposed; implementation awaits one combined design/plan approval.

## Outcome

Reduce the elapsed time of evidence collection without weakening source permissions,
quotation checks, investigator attribution or independent review. Give the person a
clear account of work, retries and time spent waiting. Keep the current running
training on its existing execution protocol.

## Current behavior

`core/studio_core/research_contract.py:Workflow.run` alternates one complete author
job with one reviewer job, for up to three rounds. The author both investigates and
writes the full report. Correction rounds receive the preceding dossier and review.

Training Studio's older question-based path already uses `AT_ONCE = 3` and a bounded
executor in `runner/engine.py`. The schema-2 synthesis branch returns before that
executor. Increasing the number of simultaneous trainings does not parallelize
research within a training.

The coordinator presently requires every fact to name the one author invocation.
Harness Research itself supports facts naming their actual investigators and
requires a reviewer distinct from the save worker and every fact author. Parallel
collection therefore needs a verified investigator registry, not fabricated author
labels or relaxed helper validation.

## Execution

For new research with multiple approved planning questions:

1. Assign independent parts of the approved scope to at most three investigators.
   Reuse the approved questions and purpose; do not add another planning model call.
   Use fewer workers when the work does not divide usefully. Each worker uses
   Harness Research's investigation guidance and receives the overall purpose,
   assigned questions, permission boundaries and relevant supplied material.
2. Run investigators in separate configured harness contexts with unique work
   directories and actual invocation identities. Each returns evidence with exact
   source captures and quotations, limitations, counterevidence and gaps. These
   packets are intermediate evidence, not independently approved reports.
3. A single coordinator validates and checkpoints each packet as it arrives. It
   assembles one immutable evidence registry. A synthesis worker writes the connected
   findings, report and brief from that registry using Harness Research guidance.
4. Run a separate independent reviewer against the exact saved dossier and originals.
   Existing Harness Research checks remain the publication boundary.
5. Route corrections to the affected investigator packets or synthesis passages.
   Keep verified, unchanged packets; refresh sources only when required by the
   person's request or evidence validity. Every changed final dossier invalidates its
   review and needs the helper's complete independent review again.

A small single-scope request can keep the existing combined author/reviewer path.
Parallelism is bounded; no one-job-per-question fan-out and no mandatory extra
approvals are added to the writing workflow.

## Source identity and attribution

- Bind every packet to the approved input/scope fingerprint, execution generation,
  source permissions, actual investigator identity and captured bytes.
- Namespace source and fact IDs deterministically within the helper's ID limits.
  Rewrite only schema-defined reference fields. Never rewrite quotations or prose
  by text replacement, infer a citation, or silently drop a conflicting claim.
- Retain individual fact authors. The synthesis worker cannot relabel investigator
  facts as its own or introduce unregistered authors. Any permitted new synthesis
  fact must have its own real author, captured source and exact quotation.
- Coalesce captures only when identity, origin, permission, context and original/
  capture hashes agree. Equal URLs or text alone do not establish equivalent sources.
  Preserve distinct versions and conflicting evidence.
- Use one coordinator for shared state, registry writes and final saves. Workers do
  not concurrently mutate one Harness Research case or the team repository.
- Keep private intermediate material in confined local storage. Publish only through
  the existing reviewed handoff/sharing boundary.

## Limits and recovery

- Default maximum: three investigator contexts, bounded by the studio's existing
  worker capacity. Reserve time and supported monetary budget for synthesis and
  review before dispatching collection; concurrent workers cannot each claim the
  entire remaining allowance. Do not increase configured limits automatically.
- Preserve existing provider-specific accounting limits: when dollar cost is not
  reported, show that it is unknown rather than promising a hard dollar ceiling.
  Parallel work may use more total tokens even when it reduces elapsed time.
- Pause stops dispatch and lets in-flight work reach safe checkpoints. Stop cancels
  this execution's workers using the existing process-identity safeguards. Completed
  valid checkpoints remain available.
- Retry only missing, refused or invalidated packets. Crash recovery validates input
  fingerprints and captured hashes before reuse. Cancelled, stale, partial or
  unvalidated responses never become published evidence through recovery.
- Changing inputs or permissions invalidates the affected work explicitly. Never
  broaden source access to complete a failed workstream.

## Progress and timing

Keep the main view simple: Investigating, Combining findings, Independent check,
Ready for review. Show meaningful workstream progress and which job is active;
retain pause/stop and an optional details view. Do not claim a percentage or a fixed
finish time without supporting measurements.

Distinguish elapsed time since the training started from active wall time, waiting/
stopped time, and cumulative assistant time. Active wall time is the union of
recorded worker intervals, including live intervals; overlapping workers must not
inflate it. Assistant time is the sum and is labelled separately. Missing historical
timestamps produce an explicit limitation, never invented paused-time precision.

Use the existing Golden Gate-inspired components and opaque reading surfaces.
Do not add mandatory agent-management controls to the main training flow.

## Compatibility and delivery

First enable the new execution protocol in Training Studio. Put common orchestration
and identity boundaries in shared core; research semantics remain owned by Harness
Research. Keep Presentation Studio and Blog Studio on their existing execution mode
until their adapters are explicitly enabled and verified.

Record an execution protocol per new run, separately from the pinned companion
capability. Existing serial runs, history and saved research remain readable and
resume serially. No running job is migrated or restarted automatically. Switching
an existing run, if later supported, is explicit and allowed only at a safe stop.

No automatic companion updates, new provider, library, frontend build, or budget
increase is part of this design.

## Acceptance and performance evidence

- Barrier-based synthetic tests demonstrate that independent investigators overlap
  and respect the worker bound. A matched serial/concurrent benchmark reports
  collection time, synthesis/review overhead, token/cost availability and failures.
- Real helper tests verify exact quotes, source permissions, bounded IDs, mixed
  investigator attribution and a genuinely separate reviewer context.
- Exercise partial failure, stopped jobs, stale inputs, concurrent budget reservations,
  cross-stream ID collisions, contradictory captures and restart/retry checkpoint reuse.
- Check legacy-run resume, timing of paused and overlapping intervals, and mobile
  progress/pause/stop/retry without duplicate jobs.
- Run the relevant full suites once for the integrated feature in a disposable Tart
  environment. Use no personal state or live provider jobs during verification.
- Measure a representative live run only as a separately authorized action. Do not
  promise a threefold end-to-end speedup: synthesis, review, provider latency and
  uneven research work remain on the critical path.
