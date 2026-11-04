# Marketing Studio Brands: repository ownership and Plan 7 completion

Addresses #310. The existing Brands implementation on the unfinished Harness Brand branch is reused selectively; its historical team-storage authority and studio environment overrides are not imported. The owner has authorized specification, implementation, verification and integration of remaining issues.

## Contract

- `brand.brands` and `studio_core.brand_data.place` alone select the repository. Reading Brands never clones, updates, initializes a repository or launches an assistant. A missing remote copy points to the explicit Get brands action. Team storage is unrelated.
- Sources → Extract → Review → Save operate on disposable working copies in Marketing Studio's data directory. All assistant parts need exact-content review; deterministic extraction does not request an assistant. Existing worker confinement is retained.
- The list reads bounded metadata without a validation process per brand. It labels validation honestly. Save performs authoritative Harness Brand checks and sealing.
- Reject symlinks and special files in copied trees, unsafe working-copy identities, path escapes, stale storage and selected-brand dirty files. Source and archive reads are bounded. Atomic temporary files use unpredictable names.
- Save commits exactly one selected brand or icon library, plus a new standard `.gitattributes` if needed. An isolated Git index preserves unrelated staged work; failed commits restore the prior selected folder and retain the working copy for retry.
- Push is a separate, explicit yes to a disclosed repository, branch and exact outgoing head. A changed preview is refused. Refuse outgoing commits outside brand/library scope or commits mixing multiple brands. Push never forces, fetches or switches repository authority.
- Forms and reading surfaces are opaque. Use the shared shell, responsive tables, 44 px controls, semantic labels and visible keyboard focus. Preserve other local form edits and focus during task polling.

## Implementation and verification ownership

1. Import only the Brands modules, UI and disposable stand-ins, adapting existing shared setup without changing native pipeline code or the studios' environment.
2. Add abuse fixtures for configuration authority, filesystem containment, one-brand commits with unrelated staged files, rollback, changed push previews and missing consent. Independently inspect the pre-existing implementation against those boundaries.
3. Exercise the real protected Marketing Studio page at 1280 and 390 px, light/dark, keyboard and reduced effects: create/upload/extract/review/save, continued working copies, remote refusal and no push without a separate action. No provider, signed-in profile or actual brand repository is used.
4. Run the shared suite and all four native suites and packaging/launch acceptance through the existing Tart runner. Native source remains unchanged, but the shared setup shell is delivered to every studio. Retain exact tested source and sanitized results here; operational logs/screenshots stay outside the repository.
5. Publish and merge the scoped PR after verification. Record #310's final review and test evidence, then close it.

## Boundary review findings to resolve

The earlier implementation derived storage from team checkouts, used predictable save/temporary paths, followed symlinks when copying, discarded the old target before Git commit, and pushed the branch's full undisclosed head. These are addressed in this implementation and covered by disposable regression fixtures. Real brand source interpretation quality is not inferred from stand-ins.
