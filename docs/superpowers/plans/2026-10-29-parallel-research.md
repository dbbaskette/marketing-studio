# Bounded parallel research: implementation plan

Status: proposed. Contract: `../specs/2026-10-29-parallel-research.md`.

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
