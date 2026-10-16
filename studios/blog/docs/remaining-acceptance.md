# Current backlog and verification

The baseline is Blog Studio 2.1: a page with Home, Blogs, Status and Settings,
guided writing modes and stage approvals, plus the same work through the skill.
The permanent launcher and computer checks follow Training Studio. Shared team,
author, assistant and brand settings come from `studios-config.json`; limits and
writing preferences remain local. See [shared studios](shared-studios.md).

## Next implementation sets

| Order | Scope | Tracking |
| --- | --- | --- |
| 1 | Guard shared Settings saves and team activation; reload and retry stale forms without losing local writing preferences | [#98](https://github.com/dbbaskette/blog-studio/issues/98) |
| 2 | Define a compact result/error contract for save, share, busy and usage; update page consumers and skill examples together | [#81](https://github.com/dbbaskette/blog-studio/issues/81) |
| 3 | Document current optional Google support, then choose one simplified operation; keep normal page stages independent | [#78](https://github.com/dbbaskette/blog-studio/issues/78) |

The first set is implemented in this change. Its plan covers displayed-value
checks before joining, a second check before activation, explicit form reload,
unsupported-assistant preservation, and regressions for migration concurrency
and a missing clone. See [the verification record](shared-settings-validation.md).
The later sets remain planned work, not delivered features.

The [reliability epic](https://github.com/dbbaskette/blog-studio/issues/74) tracks
remaining page, sync, installer, privacy and guidance refinements. The
[capabilities epic](https://github.com/dbbaskette/blog-studio/issues/75) tracks
pre-publish reports, planning and optional integrations. Each issue now separates
work delivered in 2.0/2.1 from remaining scope. Old line numbers and measurements
are historical observations, not evidence of a current defect.

## Verification policy

Use content and link checks for wording-only changes. Use targeted regressions
at behavioral milestones and the existing Tart runner for full verification.
Storage/synchronization/installer changes also follow the real-CLI synthetic
walkthrough required by [AGENTS.md](../AGENTS.md) and
[Hub acceptance](hub-acceptance.md). Preserve local work, explicit approvals,
source/voice/brand snapshots, driver ownership and honest sharing status.
Workflow files require explicit owner approval to change.

## Historical acceptance

The owner requested closure of live-evidence-only issues #8, #9, #10, #11, #14,
#15 and #44, together with their aggregate issues #3 and #29. They are closed
without a claim that every live scenario passed. They are not prerequisites for
new implementation; observed problems can be filed as bugs.

Earlier evidence remains useful for the cases it actually exercised:

- [Issue/provider acceptance](issue-validation-2026-10-03.md): the recorded Codex,
  Google and single-account Hub subset.
- [Usability acceptance](usability-validation.md): earlier synthetic CLI routes
  and their explicit coverage limits.
- [Shared studios validation](shared-studios-validation.md): synthetic clones,
  claims, offline recovery and CLI journeys.
- [Google capabilities](google-capabilities.md): connection and support boundaries.
- [Performance workloads](performance.md): local synthetic measurements.

Synthetic clones do not establish multiple-account permissions, and recorded
Google responses do not establish live-provider acceptance. Any future live
work requires its own selected scope and authorization for external operations;
keep private content and identifiers out of this public repository.
