# Responsiveness contracts for the audit roadmap

This records the Week 1 baseline. For implemented companion capabilities and
current compatibility, see [research synthesis](research-synthesis.md) and the
[final integration evidence](audit-integration-evidence.md).

The Week 1 compatibility check reads the exact companion revisions in
`pins/companions.json`; it changes no helper, installed skill or saved project.

## Harness Research

The pinned 1.1.0 collection protocol supports bounded research areas and retained
investigation results. The coordinator can collect section contributions and
assemble one schema-2 dossier. Its independent-review template is bound to the
whole dossier digest and requires coverage of every source, fact, finding and
prose item. It does not expose reusable independent section-review receipts.

Consequently #297 can map approved teaching sections to supported collection
areas without a companion protocol change. #305 can parallelize authoring and
retain completed section contributions, but independently checked sections need
a companion capability before the studio can reuse them as final evidence. Until
then the final assembled dossier still requires the supported whole-dossier
independent check. Do not weaken that check in a studio to simulate partial review.

An identical synthesis save currently invalidates its prior review. #318 needs a
canonical companion change that checks all evidence/context identities. Old saved
tasks retain their pinned behavior. A new capability must be released, pinned and
tested before a studio requires it; updating an installed skill copy is not a fix.

## Harness Slides

The pinned 0.16.0 review preparation reuses images for unchanged slide fingerprints
and compatible renderer identities. Across whole-deck revision changes it retains
prior checks as iteration evidence rather than final approval. Presentation Studio
also has its own verified unchanged-slide coverage in `build.review_work`.

#325 should align these receipts, preserving brand, renderer, source/content,
design and review-question identities. Whole-deck consistency and exact-revision
delivery remain separate requirements. Image reuse never proves user approval.

## Week 1 timing

The existing private Activity journal now records allowlisted accepted, queued,
working, saved-result, checking, waiting-for-person and stopped boundaries. Native
run saves reuse their existing accepted and successful-attempt timestamps. It
records no new prompts, sources or raw provider events. The journal retains bounded
job history and milestones; opening a page or reading progress starts no work.

The Activity log shows elapsed time, wall time with an assistant active (parallel
calls count once), recorded checks, recorded queue/person wait, first saved result
and saved-result count. An intermediate saved result can still require checks and
approval. Unknown boundaries are shown as not recorded, not as zero or a predicted
completion time. Old logs without checkpoints retain their original activity view.

These measurements describe recorded workflow boundaries, not live-provider speed
guarantees. Future section orchestration must keep the same distinction between
saved intermediate work, independently verified evidence and final human approval.
