# Parallel research checking implementation plan

Contract: [specification](../specs/2026-11-05-parallel-research-checking.md).
Execute one issue and merge its verified PR before starting the next.

1. **#377: final brief bounds and role.** Own `research_sections.py`, its tests and
   the incremental-workflow guide. Cover configured caps, explicit grants, final
   timeout naming, successful-section retention and exact evidence validation.
   Verify shared contract tests and affected native transport behavior with the
   pinned helper. No live provider jobs.
2. **#378: Harness Research team-review contract.** Define capability/schema,
   deterministic assignment and receipt validation in Harness Research; cover
   malformed, missing, duplicate, stale and non-independent review identities.
   Preserve legacy review validation and bind verification to exact artifacts.
   A compatible pinned runtime is required before native dispatch can use it.
3. **#378: host execution.** Add bounded review-unit dispatch and durable receipt
   reuse to the shared research workflow. Extend native/Blog adapters with distinct
   invocation IDs, shared reservations, cancellation and scoped result validation.
   Retry only invalidated work. Use synthetic slow workers to compare serial and
   parallel elapsed time and count redundant reads/jobs. Merge the issue only when
   its complete supported runtime and adapter path has passed integrated checks.
4. **#379: progress and recovery.** Extend shared progress and UI contracts for
   final assembly and review units. Exercise desktop/phone and legacy states with
   synthetic fixtures; make timeouts and retry ownership explicit.
5. **Documentation.** Update workflow/runtime guidance and evidence with the final
   supported behavior and adoption boundaries. Reuse unchanged test evidence;
   broader shared runtime checks belong to the integrated #378 milestone.

The primary implementer owns verification throughout. Initial local diagnosis may
read run metadata but public evidence must use synthetic content. Never publish
private source text, links, user project identities or machine records.

## Completion record

- Investigation: confirmed concurrent collection/section authors and serial final
  assembly/review in current source; no active-run mutation.
- #377: implemented in PR #380. Source `07adbe0d` passed 1,050 shared tests
  (one unrelated real-PDF-tool skip), 17 affected Training Studio tests and three
  Presentation Studio native transport tests in disposable macOS 27 Tart. The
  focused 11-test research check also passed. Final-only retries preserve all
  successful sections and collection work; no user run was changed.
- #378 and #379: planned; not implemented or claimed available.
