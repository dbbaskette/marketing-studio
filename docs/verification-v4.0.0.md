# Marketing Studio 4.0.0 verification

All required verification outcomes passed against the consolidated application.
Runtime code is revision `91de30dade127719fcaa673f757350ff26df39ec`.
Revision `7eb2261c8dcc047938d15e23522be2628db41ed1` adapts the brand-neutrality
test to the parent Git root; `ab0446c` fixes the CI fixture location and updates
its documentation. Neither changes application behavior.

## Native suites

A disposable macOS 27 guest ran Python 3.13.15, Node.js 22.23.2, and Git 2.54.0.
The original base was not changed. Test suites used synthetic data, local Git
repositories, isolated settings and disposable processes.

| Outcome | Result |
| --- | --- |
| Marketing Studio, CLI, shared core and installer | 48 tests passed |
| Blog Studio native suite | 511 tests passed; pinned Ruff checks and package/build validators passed |
| Presentation Studio native suite | 1,233 tests; package validator passed |
| Training Studio native suite | 1,996 tests passed; package validator passed |
| Presentation Studio brand neutrality | Both checks passed in the same guest after adapting parent-Git-root discovery |
| Native setup and launch | All three studios prepared, served their pages, reused owned processes, and stopped cleanly |
| Synthetic Hub journey | 41 steps passed |
| Synthetic shared-studios journey | 41 commands passed |

The Presentation Studio full run initially skipped the two brand-neutrality
checks because they expected a separate repository. Those same checks were then
adapted and passed separately in the guest. Combined evidence covers all 3,788
unique test cases without leaving those gates skipped.

## Diagnosed failures

Clean-machine testing exposed a Blog Studio startup delay in the standard HTTP
server's reverse DNS lookup. Blog Studio now shares the existing loopback bind
method while retaining its public server interface; a regression test rejects
hostname resolution during startup.

The collaboration fixture initially used the VM's shared results mount as a Git
working directory and failed at a handover. The same application passed both
journeys after moving active Git fixtures to disposable guest storage. Reports
are copied to the results mount after commands finish. Unchanged native-suite
evidence was reused while rerunning setup, launch and both journeys in a fresh
disposable guest. Each test VM was stopped and deleted; private logs remain on
the test host.

## Distribution and preservation

Tests cover deterministic full/subset ZIPs, source-independent native commands,
repeat installs, failure restoration, rollback, active-work refusal, and retention
of native workspaces/settings. Shell bootstrap tests use stand-in package managers
and assistants; no host packages, accounts, or provider jobs are involved.

Original studio checkouts were compared byte for byte against their preserved
import branches. Their files were unchanged, including unfinished Blog Studio
work. Namespaced tags and branches retain historical development references.

No signed-in provider, Google delivery, multi-account collaboration, or actual
assistant sign-in was claimed. Legacy queued GitHub jobs were not counted as
passing checks. The consolidated repository's verification was performed locally.
