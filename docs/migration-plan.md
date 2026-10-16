# Studio repository consolidation

Approved scope: import all three studios with history; verify independent operation;
extract shared infrastructure; unify dependencies and installation; retire the old
repositories after verification.

## Sequence and acceptance

1. Import committed histories under `studios/blog`, `studios/presentation`, and
   `studios/training`. Prefix old branches and tags. Preserve unfinished source work
   on a separate migration branch. Original checkouts remain untouched. Prove each
   imported main tree is byte-for-byte identical before behavioral edits.
2. Keep each studio's native tests, commands, guidance, and data locations. Prefer
   bundled studios from Marketing Studio's catalog and make acceptance independent
   of sibling checkouts.
3. Extract settings storage, common server protections, and identical styles into
   shared modules/assets with compatibility adapters. Preserve product-specific APIs
   and tests. Do not merge studio pipelines or drifted engine implementations.
4. Keep one companion pin set. Build self-contained suite and individual archives
   with shared files resolved. One installer can install any subset using native
   studio installers, retaining data and independent launchers. Exercise install,
   repeat install, rollback, and non-interference using disposable homes.
5. Run all relevant suites through the shared disposable macOS runner, plus native
   setup/launch and synthetic Hub acceptance. Publish verified release archives and
   sources. Transfer open issues, preserve old release downloads, add migration
   notices, and archive old repositories. Do not delete local checkouts or user data.

## Progress

- Initial audit: Marketing Studio checkout clean. Presentation Studio and Training
  Studio checkouts clean. Blog Studio has unfinished harness-research work and no
  open pull request. Preserve it separately; do not integrate it into main.
- GitHub audit: no open pull requests across the four repositories. Sixteen open
  issues need transfer before retirement.

## Verification ownership

The root check script owns the suite outcome and invokes each studio's native
checks. Native acceptance owns standalone settings and launch behavior. Installer
integration tests own bundle contents, isolated installs and data preservation.
The shared Tart wrapper owns VM lifecycle and retains environment/test logs.

- Histories imported, namespaced branches/tags retained, and source-tree hashes
  matched before behavioral edits. Original source checkouts were not changed.
- Shared storage, server protections, companion installation, and identical page
  assets extracted. Targeted native settings/security/desk/package tests passed.
- The suite builds deterministic full and subset installers. Isolated tests cover
  individual installation, independent native commands, repeat installation,
  rollback, failed-install restoration, active-work refusal, and content retention.
- Additional authorized scope: generated README header, first-run documentation,
  and a simple CLI with private reuse of the running application.
- Full native suites and clean-machine verification passed. The complete evidence
  is in `verification-v4.0.0.md`. Publication precedes issue transfer and retirement;
  the final cutover record identifies the transferred issues.

- Cutover completed: Marketing Studio 4.0.0 and all four installer archives are
  published. All five historical product tags and preserved branches are public.
  Sixteen issues transferred with product labels and original references retained.
  All three legacy repositories now have migration notices and are archived;
  their historical releases remain available. Original checkouts were unchanged.
  See the [issue map](migration/issues.md) and [retirement record](migration/retirement.json).
