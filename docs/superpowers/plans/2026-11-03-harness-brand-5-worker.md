# Harness Brand Plan 5: The Worker the Studios Call

**Goal:** Harness Brand answers every brand command the studios run, from brand packs, as a
drop-in replacement for Tanzu Brand, and installs and packages itself as Marketing Studio
expects.

**Specification:** a survey of every call the studios make (exact argv, the JSON fields and
phrases they read, exit codes, environment per caller, discovery, release and installer
rules, and Harness Slides' contract rules), kept in the session's scratchpad as
`brand-interface.md`. Where the studios' stand-in and Tanzu Brand differ, the stand-in is the
specification, except blog contracts and voice profiles, which Blog Studio and Infographic
Studio need and the stand-in refuses.

**Spec:** [2026-11-03-harness-brand-design.md](../specs/2026-11-03-harness-brand-design.md),
sections 4 and 5. Earlier plans: [1](2026-11-03-harness-brand-1-icon-libraries.md),
[2](2026-11-03-harness-brand-2-pack-extraction.md), [3](2026-11-03-harness-brand-3-pack-authoring.md),
[4](2026-11-03-harness-brand-4-real-packs.md).

## How it was done

Four steps, each written and tested directly, then reviewed independently before merging:

| Step | Commands | Pull request |
|---|---|---|
| 5a | `brands`, `contract export` (slides and blog, voice profiles), `contract check`, `layouts`, `doctor`, `data --set` | dbbaskette/harness-brand-skill#7 |
| 5b | the native icon deck, `icons` | dbbaskette/harness-brand-skill#7 |
| 5c | `presentation` (the brand audit), `guidance`, `look samples` / `choose` / `status` | dbbaskette/harness-brand-skill#8 |
| 5d | `SKILL.md`, `install-mac.mjs`, `install-skill.mjs`, `package.mjs`, README | dbbaskette/harness-brand-skill#8 |

Tanzu Brand's own modules (`brand-contract.mjs`, `look.mjs`, `skill-guidance.mjs`) were the
reference; Harness Slides' own modules give the contract its revision and check it, and
compile, render and preview look samples, so the two never disagree.

## Decisions

- **The brands folder** comes from `--data`, `HARNESS_BRAND_DATA`, or a pointer file
  (`~/.config/harness-brand/data`) written by `harness-brand data --set` or by the installer
  when it is given `HARNESS_BRAND_DATA`. Infographic Studio passes almost no environment, so
  the pointer file lets every caller find the packs.
- **`brands --json` with no usable pack is a refusal** with the reason, so a studio shows why
  instead of reporting the skill as broken.
- **The icon deck** is built from each glyph library: one disc and one white glyph per icon,
  stored uncompressed so every build gives the same bytes, kept in
  `~/Library/Caches/harness-brand/<key>/`, carried hashed in every slides contract, and made
  again by `contract check` when the cache was cleared. Icon ids are `<library>.<slug>`
  (`vmware-functional.cloud`) and stay the same across rebuilds.
- **Installing** keeps each release in `~/Library/Application Support/Harness Brand/versions/
  <version>` with `current` pointing at it, and links the Claude Code, Codex and `~/.agents`
  skills folders to `current`, as Tanzu Brand does, so Marketing Studio finds it first.
- **apply-brand stays** in the repository, unchanged. Replacing it with a Node restyle built
  on packs (spec section 4, `restyle`) is a follow-up: it is 2,300 lines of Python, and the
  person's TrueSource branch builds on it.

## Outcome

216 tests. Checked with the real Harness Slides 0.16.0 and the four real packs:

- Every brand and variant exports a slides contract, live and reading, and a blog contract
  that Harness Slides accepts. Each passes `contract check`, and its colours and slide values
  match Tanzu Brand's apart from what the packs deliberately add.
- All 894 icons load through Harness Slides' `native_group`. A composed slide on the Tanzu
  Division template placed solid, outline and plain icons correctly.
- `look samples --preview local` drew three Tanzu Division looks with icons and a contact
  sheet, and `look choose` wrote the outline.
- A fresh install into a throwaway home is found by Marketing Studio's own discovery as
  Harness Brand 0.1.0 with four brands.

### Carry-overs

- Plan 6: every studio path that runs the brand command passes `HARNESS_BRAND_DATA`.
- Plan 8: set the version to 1.0.0, package, tag and publish the release.
- Follow-up: the Node `restyle` (apply-brand on packs); `scripts/build_presentation_bundle.py`
  and `scripts/local_bundle/` in Marketing Studio still build Tanzu Brand bundles.
