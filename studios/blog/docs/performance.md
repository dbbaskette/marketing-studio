# Performance: runtime 1.8 / epic #28

## Measurement first

[PERF1 #35](https://github.com/dbbaskette/blog-studio/issues/35) established the
baseline before changing runtime code, on main `363ebcabb715eff759d77e3f1c03059568a5da30`.
The same synthetic workload exercises resume, mechanical proofreading, Google
push/pull checkpoint logic, and a private Hub sync with a local bare Git provider.
No account, live Google transfer, model request, or private manuscript is involved.

Environment: macOS/Darwin 27.0.0, arm64, Python 3.12.11. Article: 24 sections,
40 attached synthetic reference sources. Each operation has one first-use sample
and three warm samples in the same prepared process. “Cold” means first use, not
a flushed filesystem cache. Timings include cProfile overhead. Compare equivalent
hardware, workload, interpreter, and cache state; wall-clock thresholds are not CI
assertions. Small differences are noise, not claimed improvements.

| Local operation | Before: cold / warm median, ms | 1.8: cold / warm median, ms | Warm subprocess calls |
| --- | ---: | ---: | ---: |
| resume | 194.0 / 182.3 | 107.2 / 99.9 | 4 → 2 |
| proofread-mechanical | 102.2 / 102.3 | 117.1 / 10.8 | 0 → 0 |
| push-checkpoint | 15.9 / 15.7 | 18.0 / 18.1 | 0 → 0 |
| pull-checkpoint | 39.0 / 37.1 | 26.6 / 26.2 | 0 → 0 |
| hub-sync | 2288.9 / 800.5 | 2437.1 / 827.2 | 12 → 12 |

Resume returns about 3.8k characters instead of 10.1k (roughly 63% less) on this
workload, with one helper invocation instead of separate context/status commands.
Git reads drop from four subprocesses to two. These calls read the local cached
Hub tree; remote fetches are still required for a current shared-state claim.

Warm mechanical checks reuse the exact-input result, avoiding repeated paragraph
comparison. Cold checks include fingerprint/cache overhead and are slightly slower.
Pull checkpoint work benefits from single-pass evidence reads. Push and Hub sync
show no demonstrated latency improvement; their freshness and concurrency steps
remain intact. This is not a claim that end-to-end writing or Google transfers are
this much faster. Semantic proofreading remains model work outside these fixtures.

[Baseline samples](performance/baseline.json) and [1.8 samples](performance/runtime-1.8.json)
include elapsed time, top local self-time phases, read-method calls, subprocess
calls, response characters, environment, and selected guidance size. Read-method
counts are function calls, not physical disk-I/O measurements. The five listed
route files form a guidance-size sample; conditional references and host context
are additional. Character ÷ 4 estimates are labeled separately from measured
model tokens, which are unavailable. Provider/model latency and harness tool-call
telemetry are also unavailable, not zero and not billing estimates.

## Reproduce and remove diagnostics

```sh
python3 scripts/performance/benchmark.py --optimized --output /tmp/blog-studio-performance.json
```

The bounded report contains only synthetic counts, timings, and environment
metadata. It records no manuscript, identity, credentials, raw process output, or
workspace path. Delete the output JSON to remove it. Repetitions are limited to
2–10; default 3. To reproduce legacy behavior, use the benchmark script against
the baseline source tree without `--optimized`. The final report includes a hash
of runtime Python source. No telemetry service or background measurement runs.

Budgets for this fixture, derived from these measurements: resume under 150 ms
warm and 5k output characters, no more than two local Git subprocesses for a
plain status resume; warm mechanical checks under 30 ms; pull checkpoint under
50 ms. These are investigation thresholds on this environment, not service-level
promises or flaky timing gates. Keep correctness and bounded output as CI gates.
Rebaseline before evaluating other machines or larger Hub histories. Further Hub
sync optimization needs its own measured benefit; we did not remove safeguards
for a marginal timing difference.

## What changed

- **PERF2 #36:** `resume` returns compact context and a status card together.
  `context --compact` pages selected source metadata. `passages` returns bounded,
  exact excerpts with hashes, offsets, origin, and selected source revisions.
  Original documents, full context, active rules, and complete artifacts remain
  available. Whole-document work must still read the whole document.
- **PERF3 #37:** completed mechanical checks, UTF-8 HTML extraction, and paragraph
  indexes have local versioned caches. Mechanical checks key the whole draft,
  attached-source pins and evidence bytes, selected voice and its guide/rules,
  article/team memory pins, guidance, explicit rules, and check version. Any draft
  edit invalidates the whole mechanical result because duplicate detection spans
  paragraphs; this conservative policy also invalidates moved/deleted locations.
  HTML extraction keys original bytes, format, and extractor version. Plain text
  decoding remains uncached because a disk cache would cost more than decoding.
- **PERF4 #38:** evidence hashing/readability share one content read; factual
  readiness uses that same evidence state. A Hub status view reads one validated
  tree for graph, intents, and browsing links. Resume reuses local bytes only
  within one bounded operation, checking file identity, size, mtime, and ctime
  before reuse. No provider response or remote write guard enters this cache.

## Existing caches audited and retained

Guidance already uses immutable task/revision pins, integrity verification,
trusted-source constraints, and runtime compatibility checks. Do not add a
second download or reopen all guidance during resume. Reuse selected guidance
only for that pinned task; a deliberate adoption uses the new revision.

Existing review records track draft/voice/evidence/guidance/memory freshness and
preserve current, stale, failed, unavailable, and not-run statuses. The new cache
only accelerates deterministic diagnostics; it does not turn those diagnostics
into an editorial verdict or overwrite a saved review.

Runtime integrity and CLI sign-in remain explicit readiness observations, never
cross-session cached success. Google capability/status observations remain
historical; identity/configuration/environment changes require a fresh check.
Fresh native reads, revision-guarded writes, readback, permissions checks, and Hub
fetch/merge/conflict handling retain their existing validity rules. We deliberately
do not cache account access. Slow/offline/auth-failure and concurrent-change tests
remain in the existing guidance, Google, Hub, and author-workflow suites.

## Privacy and lifecycle

Derived data is workspace-local in `.derived-cache`, never copied to the Hub or
skill repository. The directory is mode 0700; entries are 0600. Limits are 128
entries, 32 MiB total, 2 MiB each, and 30 days. Expired/corrupt entries recompute;
failed computations do not populate the cache. `cache --clear` removes derived
data while retaining originals, drafts, pins, and revision history. Cache entries
may contain extracted private text or findings, so do not upload this folder as
an attachment or import it as team memory.

## Verification and live limits

New fixtures cover exact-input reuse, extractor/check version changes, source and
voice bytes changed without metadata changes, explicit rules and memory pins,
moved/deleted passages, cache corruption and lifecycle, path escape prevention,
bounded exact excerpts, source revision selection, and another member's resume
without transmitting local caches. Existing suites exercise conflicts, unavailable
Google access, offline queues, readback failures, guidance timeouts, and packaging.

Isolated Tart validation passed all **177 tests** in **99.146 seconds** on macOS
27 / Python 3.13.15, plus both package validators, guidance inventory, newcomer
prompts, shell syntax, and offline install/check/uninstall for Codex, Claude, and
both. The signed-in author VM was not used or modified. GitHub's Linux/macOS
Python 3.11/3.13 matrix remains the required PR gate before merge. Live Codex/Claude, two-member account, and Google pilots remain separate
in #9, #10, and #15; no fixture result closes those live acceptance issues.
