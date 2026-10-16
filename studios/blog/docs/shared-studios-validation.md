# Shared studios integration validation

The implementation for #93 and #94 vendors Training Studio's workspace sync and
team primitives at revision `87981a0737bc9eb187c48b29f5ff8903620f2e89`.
`skills/blog-studio/scripts/studio_sync/vendor.json` records source paths and
hashes. Blog adapters supply the layout, runtime paths, ignore rules and guards.
The common convention in `docs/shared-studios.md` is byte-identical to the
companion Training Studio document in PR #68.

## Synthetic checks

- `python3 -m unittest discover -s tests -p test_shared_studios.py -v`: shared
  config pre-fill and local precedence, consent, unrelated-byte preservation,
  malformed files and credential refusal; two-clone claims, handover/takeover,
  offline retry, manual sharing, preserved recovery refs, selected migration,
  HTTP workspace switching, local-edit protection and publication guards. All
  11 focused tests pass, including reading while a fetch waits without holding
  the workspace file lock.
- All 152 Google regression tests pass after adding shared-layout discovery and
  the driver guard to remote-write entry points. The additional shared-workspace
  Google-driver test passes without contacting Google.
- `node scripts/ci/check-management.cjs`: page decisions, dialogs, controls,
  event wiring and element checks pass.
- `python3 scripts/acceptance/studios-journey.py --run-directory <new-directory>
  --training-checkout <training-studio-checkout>`: PASS, 41 real CLI commands.
  This uses separate per-computer data folders and a disposable bare Git remote.
  It covers join, source and voice intake, guided saves and approvals, numbered
  publication, cross-clone reading/editing, claims, handover/takeover, offline
  save/retry, an honestly unavailable editorial review, status, readable folders
  and refusal to replace uncommitted writing. The actual Training Studio helper
  joins the same repository, commits and shares a synthetic training. Blog and
  presentation files remain intact.
- `python3 scripts/acceptance/hub-journey.py --local-fixture --run-directory
  <new-directory>`: PASS, all 41 existing legacy Hub steps.
- The real `studio.py team migrate --from-workspace <legacy-workspace> --article
  <selected-id>` was also run from those two walkthroughs. One article migrated;
  all 118 source-workspace files remained byte-identical. Its original article
  files were compared byte for byte, and its immutable history was archived.
- Edited documentation links resolve. Reproducible package validation passes.

The page's join/switch behavior was exercised over actual authenticated HTTP.
Collaborative-browser navigation, opening and snapshots failed at the automation
client; no visual-browser result is claimed for this change. Tests use synthetic
content and temporary Git identities. No live provider account, private GitHub
repository, Google write or two-physical-computer pilot was used. Separate local
clones establish the synchronization behavior, not multi-account permissions.
