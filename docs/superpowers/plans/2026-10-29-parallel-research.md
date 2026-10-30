# Bounded parallel research: implementation plan

## Ownership revision — 2026-10-29

The research method, native harness guidance, evidence packet/registry contract,
validation, deterministic assembly and checkpoint semantics are proposed to move
to **Harness Research**. The replacement specification and plan are in the
`harness-research-skill` repository at
`docs/superpowers/specs/2026-10-29-parallel-research.md` and
`docs/superpowers/plans/2026-10-29-parallel-research.md`.

Marketing Studio retains the consumer integration: configured worker execution,
shared budget reservations, process cancellation, execution-protocol compatibility,
progress/timing UI and initial Training Studio enablement. Do not independently
implement packet merging or source validation here. The Harness Research proposal
includes a separate studio integration milestone.

This dated note records the ownership proposal as it stood on 2026-10-29. The
original studio-first proposal below is retained for context; its shared-core
ownership of research packet semantics is superseded by the Harness Research
proposal. Current consumer-integration status and execution details are recorded
in the Marketing Studio implementation plan. This documentation update does not
migrate or restart active runs or applications.

---

Status: approved by the user; implementation and verification in progress. Contract: `../specs/2026-10-29-parallel-research.md`.

## 1. Freeze protocol and measurement boundaries

Owner: implementer. Inspect the shared research adapter, native job bookkeeping,
Training Studio's runner/state consumers, Harness Research's validation interface
and both other studio adapters before extending the contract.

While the person's app has active jobs, implement in an isolated managed worktree.
Keep the checkout and helper files referenced by those jobs unchanged. Deployment
and any app restart wait for a safe idle point.

Relevant files:

- `core/studio_core/research_contract.py`
- `core/studio_core/research_view.py` and `step_times.py`
- `studios/training/runner/engine.py` and `pipeline.py`
- `studios/training/tests/test_synthesis_integration.py`
- `tests/test_research_contract.py`, `test_research_capture_check.py`

Define explicit execution, packet and invocation records. Keep serial protocol
behavior intact. Define active wall-time interval union independently of summed
assistant time; do not infer that every gap was a user pause. Write the state matrix
before changing readiness or status. No live run is modified.

Verification: focused tests for old job identities, old runs, incomplete timing
history and overlapping/stopped intervals. Capture a synthetic serial baseline.

## 2. Implement the evidence packet boundary

Owner: implementer; depends on 1. Use existing confined worker/capture tools in
`core/studio_core/shared_runner/worker_tools.py` and Training Studio's thin adapter.
Delegate investigation content to Harness Research guidance.

Validate packet scope, identity, source permission and bytes before checkpointing.
Implement bounded ID namespaces and schema-aware reference remapping. Preserve
actual fact authors, original/capture distinctions and contradictions. Establish the
single-writer assembled registry and immutable inputs supplied to synthesis.

Verification: real pinned helper fixtures for two investigators, ID collisions,
missing/ambiguous sources, quote mismatch, selected/public permission boundaries,
original hashes, and an unregistered fact author. No fabricated author identities.

## 3. Add bounded scheduling, budget reservations and recovery

Owner: implementer; depends on 2. Extend shared orchestration through an explicit
opt-in execution mode, enabled initially only by Training Studio. Reuse separate
native harness invocations and the existing worker bound; avoid shared mutable
round counters and duplicate job names.

Checkpoint completed packets. Dispatch at most three independent investigations,
then synthesis and independent review. Reserve shared supported budget atomically
and retain cancellation/process-identity protections. Route repair to affected
packets, retaining valid work. Review every new final digest under the existing
helper contract.

Verification: controlled concurrent workers/barriers, maximum-active count,
over-budget scheduling refusal, exhausted/unreported costs, one worker failure,
cancel/pause, stale-generation completions, process loss and local checkpoint resume.
Compare against the equivalent synthetic serial baseline; separate collection
improvement from whole-pipeline time.

## 4. Connect Training Studio and show useful progress

Owner: implementer; depends on 3. Relevant UI and tests:

- `studios/training/skills/training-studio/scripts/desk/app.js`
- `studios/training/runner/engine.py`, `page.py` and `pipeline.py`
- `studios/training/tests/test_runner_engine.py` and page harness/tests
- `studios/training/docs/superpowers/plans/2026-10-20-training-workflows.md`

Show workstreams, collection/synthesis/review phases, worker activity, preserved
checkpoints and focused retries. Label elapsed versus active versus assistant time
correctly. Keep the default flow free of mandatory scheduling controls and use
existing Golden Gate-inspired components. Preserve all existing-run semantics;
the current active training is neither converted nor restarted.

Verification: synthetic complete/partial/stopped/restarted journeys, legacy serial
resume, independent review after changed evidence, current-generation guards and
phone-width progress with functioning pause/stop/retry. Budget/review approval
screens must describe the selected execution accurately.

## 5. Integrated verification and delivery

Owner: primary implementer; one final verification owner. Use the shared Tart runner
and existing project CI wrappers. Run affected shared and native suites once after
the feature slice is coherent, plus package checks and synthetic CLI acceptance.
Reuse valid evidence for unchanged parts; rerun affected checks after corrections.
Never scan a real account HOME or use real provider/Google credentials in tests.

Record the tested source tree, environment, synthetic timing comparison and coverage
limits. Retain logs and delete disposable VMs. Keep required remote gates. Publish
the authorized PR/merge only after verification, and restart an idle studio only;
never interrupt the current research to deploy the change.

## Review focus

- Multi-investigator attribution remains truthful; reviewer context is independent.
- ID remapping cannot change quotations, permissions or factual claims.
- Parallel budgets are reserved rather than duplicated; unknown costs stay unknown.
- Failed or cancelled work cannot be adopted through stale checkpoint recovery.
- Resume avoids unnecessary repeated collection and preserves existing runs.
- Active time is measured without double-counting parallel jobs or hiding retry time.
- Synthetic concurrency results are not presented as measured provider speedups.

## Execution state transitions

| Action / condition | Saved state and next work | Verification |
| --- | --- | --- |
| New runner training | Schema 5 pins parallel protocol 1, at most 3 investigators | `ParallelNativeTests` |
| Saved serial training resumes | Original schema/transport retained | `test_saved_serial_run_does_not_acquire_parallel_protocol` |
| One investigator fails | Other checked packets retained privately; retry missing area | `test_failed_area_reuses_other_checkpointed_areas_after_restart` |
| Pause after collection | Finished packets retained; synthesis waits for resume | `test_pause_can_checkpoint_but_does_not_begin_synthesis` |
| Stop or ownership changes | Late results cannot publish checkpoint pointers | cancellation and native ownership guard |
| Capture changes / explicit refresh | Hash mismatch invalidates packet; request creates new input-bound generation | capture/refresh tests |
| Fact review objection | Only owning area recollects; whole final digest gets new review | targeted correction test |
| Prose review objection | Evidence retained; synthesis and independent check repeat | prose correction test |
| Unknown parallel protocol | Resume refused; no fallback to serial execution | native protocol regression |
| Overlapping workers | Active wall time uses interval union; assistant time uses sum | `TimingTests`, phone progress journey |

Implementation uses existing Harness Research schema 2. No helper format or published
training material format changes. Schema 5 is the runner execution record version,
so older runners refuse it instead of accidentally resuming it serially. The CLI's
existing standalone skill workflow and older run records are unchanged.

## Synthetic baseline

`scripts/ci/benchmark-research.py` runs the same nine fictional questions and facts
with one and three investigators, the pinned real helper, and fixed simulated work
per question. Three repetitions gave median collection 0.7484s / 0.2690s and whole
workflow 1.2663s / 0.7722s. Synthesis/review simulated work was 0.1230s / 0.1210s;
the remainder includes helper validation and checkpoint coordination. All six runs
completed without failure. Tokens and provider costs are unavailable: no provider
was called. This demonstrates overlap and coordination overhead, not live-model
speed or training quality. Uneven real questions and serial synthesis/review remain
on the critical path.
