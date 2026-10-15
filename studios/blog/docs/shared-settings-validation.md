# Shared Settings recovery — October 15, 2026

This change implements the Blog Studio scope of
[#98](https://github.com/dbbaskette/blog-studio/issues/98). The sibling report
was used to identify equivalent cases in Blog's adapter; this record does not
certify Training or Presentation Studio's implementations.

## Changes and regressions

- The page sends the displayed raw team/share baseline. Joining checks it before
  Git preparation and again when merging shared settings. The prepared workspace
  is remembered only after that save succeeds. A concurrent change leaves the
  previous workspace pointer and the other studio's values intact; the prepared
  folder is kept for a retry. No shared-config lock spans network operations.
- Writing, brand and team forms offer **Reload shared settings** after a stale
  refusal. Reloading displays current values and permits a new explicit save;
  it does not retry the action automatically. Local tone/research/stop/time
  edits survive reloading writing defaults. The quick share-mode action also
  checks its displayed baseline.
- Local writing saves preserve an unsupported shared assistant and its
  model/effort while continuing to display Blog's supported fallback. Blog does
  not edit the sibling studios' model/effort controls.
- Existing missing-only migration is exercised with a competing value inserted
  before the writer lock: the competing value and unrelated members survive.
  A missing clone still migrates share before removing the legacy copy.

## Commands and outcomes

```sh
.venv/bin/python -m unittest discover -s tests -p test_shared_studios.py
node scripts/ci/check-management.cjs
.venv/bin/python scripts/acceptance/studios-journey.py \
  --run-directory /tmp/blog-settings98-studios-journey \
  --training-checkout ../training-studio
```

All 24 focused regressions and the DOM event checks pass. The synthetic real-CLI
journey passes all 41 commands, recorded with exit outcomes in
`/tmp/blog-settings98-studios-journey/report.json`. It covers team join,
source/voice intake, saves/approvals, cross-clone resume/edit, driver handoff,
offline queue/retry, status, readable folders and local-work protection. The
Training helper shares a fictional training beside Blog/Presentation folders.
No private remote, real team content, provider credentials or Google write is
used. Multiple local clones do not establish multiple-account permissions.

The full native Tart checks are required on the final PR head before merge.
Historical successful checks for unchanged code remain historical evidence.

The collaborative preview opened the fresh synthetic Settings page, but its
automation snapshot failed after navigation (including an existing-tab retry).
No new visual-browser acceptance is claimed. Real DOM events and the existing
authenticated HTTP workspace-switch regression pass.
