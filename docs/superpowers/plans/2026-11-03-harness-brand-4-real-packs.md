# Harness Brand Plan 4: The Real Brand Packs

**Goal:** The four brand packs and the shared icon library, built from their sources,
checked, sealed and kept in `brands/` of `dbbaskette/tanzu-marketing-hub`.

**Spec:** [2026-11-03-harness-brand-design.md](../specs/2026-11-03-harness-brand-design.md),
sections 1 and 3. Earlier plans: [1](2026-11-03-harness-brand-1-icon-libraries.md),
[2](2026-11-03-harness-brand-2-pack-extraction.md), [3](2026-11-03-harness-brand-3-pack-authoring.md).

## How it was done

1. **Sources.** Each brand's `sources/` holds only what its pack is made from, not the
   whole design-system export (33 MB for Broadcom alone): the export's root files
   (`README.md`, `tokens.json`, `tokens.css`, `palette.csv`, `EXPORT-NOTES.md`) and its
   logo and art folders; the templates from Tanzu Brand (`assets/presentations/`); and
   Tanzu Brand's rules, recipes, deck directions, presentation profiles and the contracts
   it exports today (commit `23bebd4`, with local paths made relative). TrueSource by
   Broadcom's sources are its brand book, tokens, apply-brand description and logos from
   harness-brand-skill commit `605a6e5`, and the Broadcom template. The icon library keeps
   only the files `pack icons` reads from each export (12 MB of SVGs and Broadcom's index).
2. **Icon library.** `pack icons` over the three source folders gives 894 glyphs
   (858 + 5 + 31), as in Plan 1, now with `--source "VMware by Broadcom Functional Icons
   library, July 2025"` and a usage written for all four brands.
3. **Packs.** One agent per brand followed `references/building-a-pack.md` and a shared
   brief: `pack tokens` and `pack measure` from the sources, previews reused from Plan 2's
   drawing (identical templates), `pack scaffold`, then each judgement file finished by
   porting today's contract exactly and writing what each layout is for.
4. **Motif length.** The checker's 200-character motif limit (Plan 3) was stricter than
   Harness Slides (20,000) and than today's directions (up to 424); it became 1,000 in
   dbbaskette/harness-brand-skill#6 and the original motifs were restored.
5. **Checks.** Every colour role and slide value of Tanzu Division, VMware by Broadcom
   (light and dark) and Broadcom was compared with today's contracts by script: all match
   but VMware light's `canvasSecondary` (#EEEEEE is in no export colour; the template's
   panel colour #F4F8FA is used). Each pack passes `pack check` after sealing, also from a
   fresh clone.
6. **Line endings.** `brands/.gitattributes` (`* -text`) keeps every file byte for byte;
   without it Git would rewrite three `palette.csv` files and break their seals.

## Outcome

Merged as dbbaskette/tanzu-marketing-hub#1 (`27e70a7`): 39 MB, 2,063 files.

| Pack | Variants | Layouts (with previews) | Unsearchable |
|---|---|---|---|
| `tanzu` | light | 43 (34) | 12 |
| `vmware` | light, dark | 43 (40), 43 (38) | 14, 15 |
| `broadcom` | light | 23 (20) | 10 |
| `truesource` | light | 23 (20) | 11 |

Decisions left for the person, listed in the pull request: headline case (VMware by
Broadcom Title Case, Broadcom unset, TrueSource sentence case), bold titles against the
brand books, white text on VMware dark accent fills (3.6 to 1; `on-accent` recommended),
VMware light's panel colour, Tanzu Division's card fill, Broadcom's table header and chart
order, PNG logos for Tanzu Division, and TrueSource's missing dark variant.

### Carry-overs

- Plan 5 (contract export):
  - VMware's last house rule was written out from `stripOnly`; if the exporter also
    writes it from `stripOnly`, it must not appear twice.
  - `typography.code` comes from `fonts.mono` (TrueSource: Arial, its brand book having
    no monospace).
  - `icon.library` in the contract is built from the pack's icon libraries.
  - Tanzu Brand's contracts in each pack's sources are the reference output for the
    export's tests.
- Layouts no visible slide uses have no preview (by design).
