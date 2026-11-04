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

## Verification result

Application behavior was verified at `4c621568` and unchanged in final candidate
`82e07fc1` (tree `c1c415016e4d030c8c5631abf08519e6b296e9e3`). The disposable Tart
macOS 27.0 environment used Python 3.13.15, Node 22.23.2 and locked test tooling.
Full coverage completed for 984 shared, 258 Infographic Studio, 1,876 Blog Studio,
2,187 Presentation Studio and 3,181 Training Studio cases (8,486 total reported).
Two suite-declared PDF-reader skips retain their earlier dedicated acceptance.
Old section-list, API inventory/body and hard-stop fixture assumptions were corrected;
the affected 133 Training Studio and 11 Presentation Studio cases passed in the final
Tart continuation. No application behavior changed after the full-suite runs.

The actual protected Training Studio, Presentation Studio and shared-setup browser
journeys passed at 390/1280 px in light/dark, retaining input DOM/focus, warnings and
concurrent peer-studio choices. Existing Home, outline/story and local recovery
journeys also passed. Native/shared setup, source-independent setup, authenticated
launch/reuse/owned cleanup for every studio, the 41-step synthetic hub journey and
39-command shared-studio journey passed. All work used disposable identities,
settings, repositories and processes. No real provider, account or workspace was used.
Detailed operational logs and screenshots remain outside this repository.
