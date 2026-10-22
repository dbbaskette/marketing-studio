# Studio functionality and installation review

Marketing Studio 4.4.0 includes Presentation Studio 4.3.0, Blog Studio 4.3.0 and
Training Studio 4.2.3. See the native [Presentation Studio capability matrix](../studios/presentation/docs/capabilities.md)
and [Blog Studio capability matrix](../studios/blog/docs/capabilities.md) for task
entry points, matching commands and intentional terminal-only operations.

| Area | Result |
| --- | --- |
| Presentation Studio | Bring remembered conversation decks into the page; inspect saved inputs and model receipts; preview the editable outline as a sandboxed storyboard; provide feedback on revision-bound partial native previews |
| Presentation Studio review | Optional first draft, not checked; the check on demand or **Use this first draft**; focused repairs preserve unaffected drawings; matching clear inspection evidence may carry forward with a fresh whole-deck consistency check |
| Marketing Studio setup | Explicit installed-brand discovery and selection alongside repository/folder setup; shared settings retain displayed-value checks and the adjacent lock; independent studio setup carries through to the suite |
| Blog Studio | Contextual voice learning/management, interview-to-outline, history compare/restore, Google reconciliation, saved channel copies, retrieval/citation review and copywriting tools |
| Editorial operations | Report-only pre-publish checks, bounded topic-overlap advice, source status filters and retirement undo; compatible opt-in compact CLI outcomes and a checked command inventory |
| Training Studio | Existing independent workflows retained; recommended Harness Slides release aligned with the suite's verified pin |
| Harness Slides | Responsive wireframes, narrower verified-render cache lookup, native render evidence for dependency-bound inspection reuse, consistent checkpoint and batch guidance |
| Harness Research | Existing dependency-free runtime and revision-bound reuse reviewed; stable 1.0.0 handoff verified without changing the development release |
| Tanzu Brand | Shared checkpoint ownership and batch guidance; settled brand/direction reused; trusted install pins aligned with compatible stable helper releases |

## State and approval boundaries

Presentation Studio defaults to normal review, including older records with no
initial-review field. Explicit first-draft selection is snapshotted per run.
Validation and rendering still run; no reviewer receipt is fabricated. Draft
readiness, AI review, user acceptance and external delivery remain distinct.
Reloading, resuming and downloading do not opt a draft into AI review. Review on
demand is bound to the current native deck and is idempotent for that revision.

Feedback during section construction names the displayed slide/revision. It
invalidates only its producer's work; unrelated sections continue. Late success,
failure and question outcomes from superseded workers cannot become current.
Outside that phase the page retains the note and explains the current decision
point. Section display measurements are local and never count as approval.

Inspection reuse requires matching shared dependencies, native deck identity,
slide IDs/order, fingerprints, image hashes and the current question set, with
clear prior coverage. Changed slides and neighbors are inspected again; prior
findings cannot be carried forward as clear. Missing evidence falls back to full
inspection. The repair cap and the actual final user decision remain intact.

Blog Studio's tools use its existing worker queue, profile revisions, article
history, driver checks and sharing rules. Opening a tool starts no assistant
work. Generated text is reviewed before an explicit save. Google comparison and
acceptance write no Google document; sending feedback is a separate confirmed
operation. Text-only previews omit image payloads without changing saved files.

## Performance and installation

The 12-slide synthetic HTML storyboard took approximately 252 ms first-use and
54–67 ms warm in this review. This measures local HTML generation, excluding
outline writing, native rendering, human waiting and model work. No native or
provider latency improvement is inferred from it.

A matching scripted-worker/renderer fixture exercised both initial-review modes:

| Mode | First preview | Complete deck checkpoint | Reviewer jobs | Helper calls |
| --- | ---: | ---: | ---: | ---: |
| Standard | 1,504 ms | 2,324 ms | 1 | 20 |
| User first | 1,013 ms | 1,753 ms | 0 | 19 |

These single local fixture runs include intake and automatic synthetic gate
responses, with no human waiting. They demonstrate the skipped dispatch, not
native rendering speed, real-model latency or equal visual quality. The user-first
checkpoint remained unreviewed; downloading it did not schedule review.

The [Blog Studio storage measurement](../studios/blog/docs/performance.md)
compares current shared workspaces with legacy Hubs separately. Operation-scoped
immutable-tree reuse removed 16 Git subprocesses from the measured legacy saves;
no shared-workspace save or board speedup was demonstrated.

New local-bundle installs share the large verified tools under a directory keyed
by their complete pinned tool lock. Matching products reuse LibreOffice, Google
Cloud CLI, Git and preview dependencies; older sets remain available to existing
installations and rollback. Private Python/Node and product environments remain
independent. All four production slide-engine libraries are used; development
dependencies remain omitted rather than removing required functionality.

## Verification and scope

Verification uses disposable settings, homes, workspaces, Git identities and
synthetic content. Full native suites are combined with targeted regressions,
offline real-CLI setup/launch and cross-clone sharing journeys. Browser checks
cover Marketing Studio initial setup, Blog Studio contextual tools and narrow
layouts, Presentation Studio storyboard integration, and responsive wireframes.
Tart is unavailable on the review host; host checks do not establish Apple
Silicon VM installation or live Google/assistant/image-provider acceptance.

CMS handoff, Word tracked changes, Windows and additional provider channels stay
separately scoped proposals. The pre-publish report sends nothing externally;
topic advice changes no manuscript or decision. Existing installation
doctor/update/rollback/removal commands remain explicit operations. Generated
bundles, local source configuration and verification records remain untracked.
