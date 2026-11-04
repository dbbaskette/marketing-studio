# Harness Brand Plan 6: The brands folder in the studios' storage

**Goal:** Every studio that runs the brand command tells Harness Brand where the brand packs
are: the `brands` folder kept with the studios' storage.

**Spec:** [2026-11-03-harness-brand-design.md](../specs/2026-11-03-harness-brand-design.md),
sections 1 and 6. Earlier plans: [5](2026-11-03-harness-brand-5-worker.md).

## Steps taken

1. `core/studio_core/brand_data.py` says where the folder is. With a team repository it is
   `brands/` at the root of the studio's own checkout of it. With local Git storage it is
   `<local.root>/brands`, shared by every studio. Marketing Studio has no workspace of its
   own, so it uses local storage's folder, or the first studio checkout of the team
   repository that has one (`unplaced`, with `marketing_studio.workspaces.checkouts`).
2. The brand command is given `HARNESS_BRAND_DATA` everywhere it runs, unless the person set
   it already: the shared runner (Presentation Studio, Training Studio), Blog Studio, the
   brand catalog (Marketing Studio Settings and shared setup) and Infographic Studio's
   export.
3. When the brand skill in use is Harness Brand and the folder is missing or holds no usable
   pack, Setup's brand line says so in one sentence, with a link to the brand pack format,
   and changes nothing. Tanzu Brand is shown as before.
4. `scripts/sync_repos.py`, `sync.cfg.sample` and the repository sync guide name
   `harness-brand-skill` as the brand skill checkout to sync. A `sync.cfg` that still lists
   `tanzu-brand` keeps its Tanzu Brand label.

## Review fixes

- The brand catalog told the second brand skill a garbled folder: a local variable shadowed
  the folder after the first skill's listing. Every skill is now told the same folder, with
  a test for two skills.
- Shared settings of the wrong kind (a `team` or `local` that is not an object, a non-text
  root or repository) are taken as not given instead of raising errors the studios do not
  catch, and an unreadable studios config gives no folder.
- A `~` in a remembered workspace root is expanded before looking for its checkout.
- The local presentation bundle builder's example configs point at Tanzu Brand again: the
  builder still needs Tanzu Brand's packer and installer.

## Outcome

Merged into `claude/harness-brand-skill-release-98e863` (commits 930fb423, 87768b33 and
3c0c2481). No one's settings are changed: the person switches the brand skill's repository
in Settings to `https://github.com/dbbaskette/harness-brand-skill`.

## Follow-ups

- The local presentation bundle builder (`scripts/build_presentation_bundle.py`,
  `scripts/local_bundle/`) still builds with Tanzu Brand.
