# Desk request ordering and curation conflicts — runtime 1.12.1

Implements #54 and #57 on base `7207a9b` (including the newer save-feedback
receipts). The changes preserve the lightweight frontend, private Hub access,
article source pins/history, and existing sharing/recovery behavior.

## Delivered behavior

- Every list request captures its view, query, stage and page. A new request
  cancels the previous one; generation checks also discard late responses and
  failures from transports that ignore cancellation. Receipt reads started with
  the list share its cancellation/ownership check.
- Loading is announced and page controls are disabled. A current request failure
  keeps the previous valid result; failed pagination restores its previous
  offset, while results from a different view/filter cannot drive page controls.
- Source detail returns an expected-state fingerprint, selected source identity
  and location. Curation requires that guard and checks it under the workspace
  write lock, before checkout or mutation. A selected Hub is refreshed and its
  freshness verified before comparing the expected source state.
- Changed local tags/notes/retirement, changed shared heads and unshared local
  edits cannot be silently overwritten. A stale save returns HTTP 409. Original
  snapshots, source revision history and article source pins remain intact.
- The active dialog keeps the proposed values and disables resubmission on a
  conflict. Reload displays saved and proposed values separately; the user must
  explicitly choose retained proposals or saved values before another Save.
  Reload/compare alone writes nothing. Existing unshared edits requiring broader
  reconciliation are directed to chat.
- Trusted installer packages advertise runtime 1.12.1 so update checks can
  distinguish this patch. Guidance minimum-runtime and Hub data schemas do not
  change. Installed helpers still update through the installer.

## Verification

Disposable Tart VM: `blog-studio-desk-ci-20261004a`, cloned from the stopped
`tanzu-brand-golden-gate-base`. Only this clone received Python 3.13; the base and
signed-in author VM were untouched. macOS 27.0 (26A428), Python 3.13.15,
Node 22.23.2, Apple Git 2.54.0.

The unchanged repository guest runner `scripts/ci/macos-guest.sh` tested the final
functional source and rebuilt distributions in its own guest copy:

- **266 tests passed**, 137.493 seconds. This includes deterministic Node checks
  of the actual desk functions for reverse-order view/search/filter/page results,
  silent obsolete failures, loading/pagination and current-failure recovery.
- Two-editor fixture checks cover tags, notes, retirement, missing guards,
  shared-head changes before checkout, explicit resubmission, preserved source
  pins and protected unshared local edits. HTTP fixtures verify the 409 contract.
- Both skill validators, guidance inventory, shell syntax and newcomer checks
  passed. Real disposable installer install/check/uninstall passed for Codex,
  Claude and both, including GUI/minimal-PATH launcher checks. Quarantine
  assessment remained observational; no host protection was bypassed.
- Native browser interaction using fictional local data confirmed retained form
  values after a conflict, disabled Save, comparison without writing, explicit
  proposal selection, and successful resubmission. Browser error/warning logs
  were empty. The saved state was reported as local-only, correctly.

Local logs: `/private/tmp/blog-studio-desk-ci-results/`. Native comparison and
save screenshots are local diagnostic artifacts, not real team material.
Required GitHub platform CI is a separate publication gate.

An initial fixture exposed explicit shared inspection after the catalog hid a
shared row behind its local checkout. The implementation now reads that shared
head explicitly; the corrected focused check and the final full Tart run passed.

No real accounts, Google operations, membership changes or private drafts were
used. Multiple-member/live-provider acceptance remains separately tracked.

## Remaining work

- #56: decision-memory detail behavior; #58: read-only refresh/capability disclosure.
- #53: phone-friendly layouts; #59: article/finding continuation, focused details
  and the additional inbox-search acceptance recorded in the implementation review.
- Measured performance follow-up: one validated saved-Hub observation per request,
  then larger-history/index profiling where needed.
- Progressive/deterministic follow-up: smaller entry guidance, explicit operation
  dependencies and loading budgets, shared operation/state/action definitions.
- Live acceptance: #8/#9/#10/#11/#14/#15, remaining #39/#43/#44 acceptance, and
  aggregate #29/#3. No closed issue is treated as evidence for another pilot.

See [implementation review](implementation-review-2026-10-04.md) for priorities,
measured workload and the issue grouping. This record does not claim those other
features or live tests are completed.
