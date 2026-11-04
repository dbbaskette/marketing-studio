# Incremental polling measurement

Issue #359 compares the prior bounded scan at `3c49ee71` with resumable scanning.
Measurements use disposable synthetic files on macOS with Python 3.14. No provider
ran, and these results do not establish production latency.

Run `scripts/ci/benchmark-polling.py --baseline /path/to/previous-polling.py`.
There are three repetitions of 30 probes, using the native policy at modeled
five-second intervals and its mandatory 60-second full read. The bytes below
are modeled transfers of a fixed encoded 30-slide synthetic payload (66,002 bytes),
not captured native traffic. The signal timing is measured wall time.

| Files / projects | Median signal ms, before → after | Full reads / 30 probes | Modeled full-read bytes | Edit visible after probes |
| --- | ---: | ---: | ---: | ---: |
| 100 / 1 | 0.71 → 0.64 | 3 → 3 | 198,006 → 198,006 | 1 |
| 6,000 / 1 | 3.17 → 19.40 | 30 → 4 | 1,980,060 → 264,008 | 2 |
| 20,000 / 100 | 35.84 → 33.20 | 30 → 7 | 1,980,060 → 462,014 | 5 |

The flat 6,000-file signal takes longer because it now examines metadata instead
of abandoning the scan at the directory-entry limit. It avoids 26 of 30 full
reads; the 20,000-file/100-project case avoids 23. All measured individual scans
stayed within the 75 ms work budget. This is a reduction in repeated content
reads and transfer, not a claim that every endpoint becomes faster.

A separate native HTTP check used the authenticated Training Studio and
Presentation Studio pages with 30-slide fixtures and 6,000 synthetic files in
a different project folder. Across 20 immediate idle probes:

| Product | Signal bytes | Median signal ms | Full run reads | Full run bytes | Median run ms | External edit observed |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Training Studio | 2,641 | 15.13 | 2 | 44,804 | 8.77 | 2 probes |
| Presentation Studio | 2,641 | 15.13 | 2 | 123,808 | 69.01 | 2 probes |

These immediate probes exclude the periodic 60-second read; the modeled table
includes it. Worker counts stayed unchanged. Training Studio's small run read is
cheaper than its metadata signal in this fixture; the measured benefit there is
fewer content reads/bytes, not lower single-request latency.

## Freshness and resource limits

- An unfinished scan stays `complete: false`. A separate `cached` flag is usable
  only if a prior full scan finished less than 30 seconds ago.
- Changes become visible after a scan cycle (two probes for 6,000 files; five for
  20,000 in this sample), or through the mandatory 60-second full catch-up.
- Active jobs, explicit refresh and reconnect bypass idle suppression. Expired
  caches, scan errors and zero budgets force ordinary reads.
- Traversal never opens file contents or follows symlink targets. Skipped entries
  consume budget; nesting is bounded to 64. The engine owns one serialized iterator.
- Overlapping roots use an additive order-independent fingerprint, so duplicate
  paths cannot cancel each other's metadata changes.

For trees whose scan cycle exceeds the cache lifetime, the client intentionally
falls back to full reads until another complete scan is available.

The native Training Studio browser additionally made eight idle update requests
without rereading its run, training list or draft materials. After an external
fixture edit it refreshed once; slide 2 remained selected and worker count was
unchanged. This browser observation verifies behavior, not precise detection time.
