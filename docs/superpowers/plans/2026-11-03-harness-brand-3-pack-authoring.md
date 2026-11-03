# Harness Brand Plan 3: Checking and Authoring Brand Packs

**Goal:** A brand pack can be drafted, finished by a person or an assistant, checked and
sealed: `pack check` for brand packs, `pack scaffold`, `pack seal`, the authoring guide
`references/building-a-pack.md`, and Example Co as the test pack.

**Repository:** `dbbaskette/harness-brand-skill`, branch `harness-brand-pack-authoring` from
`main` after Plan 2 (`a468e1c`).

**Spec:** [2026-11-03-harness-brand-design.md](../specs/2026-11-03-harness-brand-design.md),
sections 2 and 3. Roadmap and earlier plans: [Plan 1](2026-11-03-harness-brand-1-icon-libraries.md),
[Plan 2](2026-11-03-harness-brand-2-pack-extraction.md).

## How this plan was carried out

The code was small and tightly coupled to Plan 2's modules, so it was written and tested
directly in a working copy, committed in four steps, and then reviewed as a whole by an
independent reviewer before the pull request, instead of task by task.

## Files

| File | Responsibility |
|---|---|
| `scripts/lib/pack/check.mjs` | `checkPack(pack, {hashes})`: every problem with a brand pack, each a sentence; `contrast`, `packFiles`, `sourceFiles`, `sha256` |
| `scripts/lib/pack/scaffold.mjs` | `scaffoldPack`: drafts brand.json (with `draft`), directions.json, audit.json and guide.md from tokens.json and layouts.json; `guessRoles` |
| `scripts/lib/pack/seal.mjs` | `sealPack`: brand.json with `files` and `sources` SHA-256 maps, once the pack passes |
| `scripts/pack-brand.mjs` | `pack scaffold`, `pack seal`, and `checkBrand` for `pack check` |
| `scripts/pack.mjs` | `pack check` takes an icon library folder or a brand pack folder |
| `tests/fixtures/pack.mjs` | Example Co: a brands folder with a finished pack and an icon library |
| `tests/check.test.mjs`, `tests/scaffold.test.mjs`, `tests/pack-authoring.test.mjs`, `tests/building-a-pack.test.mjs` | the tests |
| `docs/brand-pack-format.md` | `draft`, `files` and `sources`, the contrast rule, and the six commands |
| `references/building-a-pack.md` | the guide a person or Claude or Codex follows to finish a drafted pack |

## Decisions

- `pack check` decides by what the folder holds: `library.zip` means an icon library,
  `brand.json` a brand pack.
- A pack with no `slides` in any variant is for writing only and needs no template,
  `layouts.json`, `directions.json` or `audit.json` (the rule the format document already
  gave; the spec's table said `audit.json` was always required).
- Text roles need 4.5 to 1 on `canvasPrimary`; a type style needs 4.5, or 3 for large text
  (18 points, or 14 bold). The `section` style is not measured against `canvasPrimary`,
  since a section title sits on its section layout's own ground, often a dark one.
- `pack scaffold` marks its draft with a `draft` list in `brand.json`, which `pack check`
  refuses, so a guessed pack can never pass unreviewed.
- `files` holds every pack file but `brand.json` and `previews/`; `sources` every file in
  `brands/<id>/sources/`. Both are written only by `pack seal`.

## Trial on the real brands

After `pack scaffold` and removing `draft`, `pack check` on Tanzu Division, VMware by
Broadcom, Broadcom and TrueSource by Broadcom (on the Broadcom template) reported only
true review items: the logos to add, the icon library to place, and Broadcom's Aqua
(2.1 to 1 on white) as the metric colour.

## Outcome

Merged as dbbaskette/harness-brand-skill#5 (`b7f49b8`), 188 tests passing.

The independent review found four things, all fixed before merging: the seal now covers
`brand.json` itself (`brandSha256`, over its fields with keys sorted) and reports files
added since sealing; a malformed seal no longer stops the pack being sealed again; hand
edits of the wrong type (a string where a list belongs, `null` meanings, `toString` as a
role) give a sentence instead of a crash; and `Review:` text left by `pack scaffold` is
reported. Smaller fixes: the measured canvas is compared (within a point), logos must be
in `assets/`, and the scaffold reads a writing-only brand's font from `tokens.json`.

The format also gained the slide settings Tanzu Brand's contract gives Harness Slides today
and the format lacked: `image`, `fills`, and the further `chart`, `table`, `icon` and
`spacing` fields, so Plan 4 can port them and Plan 5 export them.

### Carry-overs

- Plan 4: port each brand's values exactly from Tanzu Brand's exported contracts (exported
  on 3 November into the session scratchpad), including fractional boxes; the canvas may be
  the measured one.
- Plan 5: the contract's `typography.code` comes from `fonts.mono`; `deck` from
  `directions.json`; `icon.library` from the pack's icon libraries.
