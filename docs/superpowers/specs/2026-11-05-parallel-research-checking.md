# Parallel research checking

Research responsiveness work: #377, #378, #379.

## Outcome

Use independent agents for separable outline areas and evidence checks. Preserve
completed work, keep a shared spending allowance, and make the remaining serial
coordination small and visible. Do not restart, migrate or spend on active user
projects as part of implementation or verification.

## Current behavior

- Collection and section combining already run at most three workers concurrently.
- Section contributions are retained independently and reused by content identity.
- Final brief assembly follows the completed contributions. Its previous default
  cap was 120 seconds while section combining normally allowed 300 seconds.
- Independent review is one invocation over every original, fact, finding and
  prose item, with a whole-report coverage/usefulness assessment.
- The current review contract binds one worker to the exact dossier digest and
  original-read attestations. A coordinator cannot honestly impersonate several
  independent reviewers under that contract.

## Design

### Final brief (#377)

Give final assembly an explicit, narrow role over completed findings and sections.
Use the saved combining allowance and any explicit final-only time grant, still
bounded by the native engine. Keep all source files available for validation.
Do not rewrite sections or run another source investigation. A timeout names the
final brief; retry retains completed sections and does not lift spending limits.

### Independent review team (#378)

Introduce a versioned Harness Research capability for a team review. Partition
source attestations and claim checks into bounded units, preferring source-local
grouping to avoid repeated original reads. Every source, fact, finding and prose
item has an explicit owner; cross-source claims carry their complete dependency
closure. A final reviewer assesses coverage, usefulness and contradictions across
the assembled report using checked units. It cannot manufacture missing receipts.

Every receipt identifies its actual worker, exact source/capture hashes, dossier
basis and assigned IDs. Reviewers must be distinct from every relevant author.
The helper validates total coverage, uniqueness, independence, input freshness and
terminal results before it accepts the assembled review. Rejected checks remain
rejected; inaccessible originals remain access failures. Content and structural
validation never substitute for semantic checking.

Use the existing maximum of three concurrent workers and shared allowance. Budget
reservations must leave room for peers and the final assessment. Stop prevents
new dispatch, cancels active jobs and rejects late results from superseded inputs.
Keep completed receipts durably; retry only missing or invalidated units. Changes
to sources, findings, prose, scope or review policy invalidate dependent receipts.

Existing tasks retain their pinned capability. Runtime upgrades and adoption for
saved tasks must be explicit; no silent migration, automatic install, live retry
or change to a user's spending policy.

### Visible progress (#379)

Distinguish section authors, final brief assembly, independent check batches and
final consistency assessment. Show observed active agents and queued/kept/failed
units with elapsed times when available. Capacity is not an active-agent count.
Use compact snapshots, not repeated full-report reads. Legacy snapshots remain
understandable and missing measurements remain unknown.

## Acceptance

- Exact-source and semantic coverage is at least as strict as the existing check.
- Synthetic equivalent workloads demonstrate overlapping invocations and lower
  elapsed checking time; report duplicated reads, job count and resource caps.
- One failed/timed-out unit does not rerun successful unrelated units.
- Stale, duplicate, missing, self-reviewed or altered receipts cannot complete.
- Cancellation, exhausted reservations and unavailable originals preserve honest
  partial state without starting more work.
- New and pinned legacy runtimes retain valid independent behavior.
- Desktop/phone progress identifies the actual bottleneck and retry scope.

## Other parallelism

Keep existing concurrent investigators, section authors and slide-section builders.
Parallelize independent work only after its inputs are fixed. Final coherence,
approval and writes to one delivery artifact require ordered ownership. Increasing
the concurrency cap or multiplying agents for small local edits is outside this
change; neither is evidence of a speed improvement by itself.
