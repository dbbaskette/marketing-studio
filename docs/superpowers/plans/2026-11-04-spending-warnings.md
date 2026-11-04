# Spending warnings (#304)

Contract: remaining-backlog spec. New projects pin warn or hard-stop from the
shared per-studio choice. Missing saved policy means hard-stop. Existing amounts,
cleared allowance, evidence and approvals are preserved. Explicit local policy
changes bind policy/limits/driver/cleared state, reject busy or stale submissions,
and start no work. Warn workers receive positive $5 budgets rather than exhausted
project remainders; Quick scan/requested smaller budgets and all time/round limits
remain. Dollar reporting/enforcement retains assistant-specific limits.

## State-transition matrix

| Trigger | Prior state | Result | Verification |
| --- | --- | --- | --- |
| New work | Shared default warn | Saved warning policy, $5 job budget | Both SpendingPolicyTests |
| Load old work | No policy | Existing hard-stop/Carry on | Saved fixtures, full native limit tests |
| Reported crossing | Warn, working/waiting | Same workflow, one durable Activity warning per crossing; desk/home notice | Shared SpendingTests, native metadata and browser journeys |
| Research exceeds amount | Warn, approved scope | Completed independently checked sections; positive job budgets | Both SectionResearchTests warning scenario |
| Individual job budget hit | Warn | Explicit failed-step retry; peer results kept | Native failure/recovery gates |
| Explicit policy save | Idle owned work, matching basis | Policy only; no model work or approval | Both SpendingPolicyTests and real browser |
| Concurrent policy/limit/owner change | Old basis | Refused without mutation | Basis/native stale tests |
| Shared other-studio change | Open form | Only edited leaf saved, peer choice retained | Real shared-settings browser |
| Continue old stop | Hard-stop | Existing explicit allowance behavior; no silent policy conversion | Existing native limit/setting-change tests |

Warnings update outside the editing DOM. Training Studio keeps the same outline
field while unrelated timing/budget data changes; other redraws restore focus by
stable key or field ID. Styles use opaque reading surfaces with an advisory edge.

Focused shared/native/pinned-helper and real-browser checks precede one complete
integrated Tart gate (all four studios because the UI/activity/settings are shared),
plus package/context budgets, existing intake/outline journeys and installer/CLI
acceptance. No provider or real workspace is used.
