# Remaining backlog implementation

Contract: [spec](../specs/2026-11-04-remaining-backlog.md). All seven open issues
were read with their comments. Implementation is authorized by the user.

1. **Launcher reliability (#308/#309).** Own marketing_studio/cli.py and existing
   launcher/CLI tests. Reuse private state, safe output and running LAN; add readiness
   observation for shell-to-assistant transitions. Fifty targeted process runs,
   complete shared suite and disposable CLI journeys. Publish and merge a focused PR.
2. **Spending policy (#304).** Own shared settings/transport/activity/UI and both
   deck-studio settings/engines/desk adapters. Inspect every job cap and stop path,
   then implement one shared policy contract with native saved-state compatibility,
   warning/stop matrix and 390/1280 light/dark checks. Complete affected suites and
   package/setup acceptance; publish and merge.
3. **Brands (#310).** Inspect the existing feature branch without rewriting it.
   Bring over only required code/tests, adapt repository authority and shared UI
   to main, review destination containment/commit scope/push boundaries explicitly.
   Complete real 390/1280 light/dark browser and shared/four-native gate; publish
   and merge. Do not change owner-approved GitHub workflow definitions.
4. **Readiness cleanup (#152/#223/#224).** Reconcile implemented capabilities and
   current offline evidence, update release documentation and prepare concrete
   synthetic live/owner acceptance steps. Consolidate redundant engineering issues
   while preserving all unmet gates in #224. Obtain separate live-use authority only
   after the action is concrete and reviewable; leave genuine acceptance incomplete.

Completion claims record tested trees and environments. No delegation is used.

## Launcher milestone

Implemented private running-home state reuse for both flags, including terminal-only
links, JSON/pipe redaction, existing LAN reuse without rediscovery, and actionable
refusal when phone access is absent. The fake assistant now waits in its shell
instead of becoming the final sleep command; the process test waits for the exact
session, start identity and assistant command and captures per-stage diagnostics.
Fifty isolated local repetitions passed, preserving wrong-start refusal, orphan
survival and matching-identity termination. The complete targeted launcher/CLI
checks passed apart from a corrected expected CLI error exit-code assertion; both
new socket cases passed afterward. Full shared/CLI acceptance follows in Tart.
