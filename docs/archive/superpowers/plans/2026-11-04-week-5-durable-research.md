# Week 5: durable combining and economical review

Authorized audit scope #305/#318, after Week 4 PR #330. Use the canonical companion
for explicit unchanged-save review retention; require a supported pinned capability
before using it. Old helper tasks keep their saved runtime and revision behavior.

New opted-in Training Studio and Presentation Studio research uses one workstream per
approved section, with at most three active investigators/combiners. Collection already
supports up to 64 streams; no protocol weakening or invented section-review receipts.
Each combining job reads only its section's deduplicated evidence and cited source
metadata. Keep validated contributions durably. A short final author reads completed
contributions for introduction, comparisons and brief, then the supported independent
check still covers the complete assembled dossier. Mark contributions as drafts until
that check passes; never call cached author output independently reviewed evidence.

Give section combining its own bounded time allowance and per-section More time.
Preserve saved model choices; existing Combining/Checking defaults are already medium.
Retry only unfinished or input-invalidated contributions. Show counts by section and
retain existing exact source, provenance, stop and terminal-observation guards.

Verify four sections with a maximum of three active jobs, a timeout preserving three
completed sections, retry calling only the unfinished section, factual deduplication
without losing distinctions, scoped time grants, actual pinned-helper verification and
no model work for an eligible identical save. Use disposable scripted providers and
full relevant local gates. Publish/merge companion and studio PRs in this cohort;
record release/pin boundaries and supported limitations explicitly.

Implementation: Harness Research [PR #31](https://github.com/dbbaskette/harness-research-skill/pull/31) and release 1.1.1 provide opt-in unchanged-save retention. The companion full clean-machine gate passed 233 tests and installer/CLI smoke. Marketing Studio pins that canonical release; installed user skills were not edited. New Training Studio schema 8 and Presentation Studio schema 6 save section policy and runtime capabilities. Older saved flows stay on their original paths. No invented per-section semantic review is reused: durable contributions remain drafts until the complete dossier passes the companion's independent review.

## Verification

Runtime commit `696f170c79ef0a35445540eac7a51a4c47dec7ae`, tree
`d3d964ecdd2436970552d9ed3d2b098f6fbe8ca5`: complete disposable macOS 27 /
Python 3.13.15 / Node.js 22.23.2 gate passed shared 964 tests (one existing
PDF-reader environment skip), Presentation Studio 2,181 and Training Studio
3,175. The unchanged real-PDF reader passed on the host in Week 4; that evidence
is reused. Both native outline browser journeys, nine workflow diagrams,
package validators, all standalone/shared setup, authenticated bridge launch /
reuse / cleanup, Hub 41-step and shared CLI 39-command journeys passed. All owned
processes and the test VM were removed. No live provider requests ran.

Initial attempts exposed a transient Git index-lock collision in an unchanged
browser fixture, then a stale helper parity-version marker. The final complete
gate passed after recording parity against 1.1.1. Synthetic concurrency and call
counts do not establish real-provider latency. Independent per-section semantic
review is not a supported receipt: the assembled dossier still receives the
supported whole-report check.
