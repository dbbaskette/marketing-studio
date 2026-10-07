# Performance and quantitative comparisons

Load for measured speed, capacity, latency or cost claims. A qualitative feature
explanation does not require a benchmark. This is an evidence lens for the existing
[factual-support check](../modules/blog-fact-check.md), not a benchmark runner.

Require enough supplied evidence to interpret the particular claim:

- Baseline and candidate versions/configurations; hardware or service size;
  workload/data size; concurrency; relevant cache/warmup conditions.
- Metric and units, sample size or repetitions, aggregation and variation.
  Identify percentiles versus means, throughput versus latency, and error rates.
- Comparable tuning and resource budgets, meaningful workload limits and the
  bottleneck actually observed. An unexplained result remains an observation.
- Reproduction method or accessible supporting artifact when available. Keep
  private logs/datasets out of the published article unless selected for release.
- Boundaries: workload specificity, setup differences and what was not measured.
  Do not project a small experiment into universal production or customer claims.

Report absolute results alongside relative changes when available. For a runtime
moving from 100 ms to 50 ms, the reduction is 50% and the speedup is 2×; avoid
ambiguous “100% faster.” This is arithmetic illustration, not product evidence.

For a cost claim, specify workload, pricing date and included cost categories;
do not derive total ownership savings from compute spend alone. Record missing
conditions as evidence gaps. Request the missing method/results, narrow the claim,
or omit it; never fabricate repetitions or a favorable chart.

Distinguish measured association from a demonstrated causal explanation. Use the
same claim locations and evidence records as fact checking, and record actual
coverage. No benchmark execution, external upload or purchase is implied.
Basis: Brendan Gregg's benchmarking checklist; [source map](sources.md).
