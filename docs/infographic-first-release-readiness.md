# Infographic Studio first-release readiness

Implementation is merged in [PR #183](https://github.com/dbbaskette/marketing-studio/pull/183)
and [PR #186](https://github.com/dbbaskette/marketing-studio/pull/186). The current native
version is **0.2.0**. Follow-up feature completion does not imply first-release sign-off.

## Verified implementation

| Area | Tracking | Evidence |
| --- | --- | --- |
| Supplied sources, located facts, three story modes and pinned brand | #138, #149, #150, #153, #156 | Exact-capture, CSV/context, requirement and source-change checks |
| Provider adapters, detailed direction, safe jobs and actual-image review contract | #151, #154, #155, #157, #160 | Injected generation/edit/inspection, ownership, secret, timeout and recovery checks; live gates below remain separate |
| Six forms, three presets, faithful editable page and four exports | #140, #158, #159, #161, #162 | Actual renderer, readable type, one-page PDF, safe SVG and exact-revision delivery |
| Desk, focused editing, history and user approval | #141, #163–#166 | End-to-end browser/CLI and late-result/stale-revision refusal |
| Shared settings, protected launch/return, native skill and distribution | #142, #167–#169 | Four-studio setup/launch, authenticated phone return and independent install/removal |
| Integrated offline verification | #170 | 686 Marketing Studio tests and 139 Infographic Studio tests passed without skips on the integrated application tree; retained Tart and native package acceptance |

The tested application tree is `4b15913e`, integrated into merged `04e05732` through
PR #186. Subsequent acceptance/documentation changes preserve that application tree.
Source-only helper fixtures, real installed PDF extraction and actual rendering are
included. Automated providers/accounts are synthetic. The independent Apple Silicon
bundle imports Word and exports all four formats after its download and Marketing
Studio are removed. No Research/Slides runtime or image/document SDK is required
for ordinary use. Detailed machine-specific logs and generated content stay outside
this repository.

## Remaining release decisions

- **#152 — Codex live execution.** With explicit authorization, generate a PNG using
  the native confined adapter and the selected signed-in Codex model. Perform a
  reference-guided edit and inspect actual returned and composed images. Saved
  events, owned bytes and the normalized outcome must agree. Never replace an
  uncertain attempt with an automatic duplicate request.
- **#223 — Visual editor and owner illustration acceptance** (consolidates #171). The
  persistent visual editor, human element names, revision states and readable history
  are implemented and covered with disposable fixtures. What remains is the visual and
  accessibility acceptance with actual artwork: present actual artwork and composed
  outputs for a conceptual illustration, illustrated process and mixed chart/art
  page. Inspect meaning, object counts/relationships, style, crop, resolution,
  label clearance, brand and factual implications. The owner makes the decision;
  renderer markers, empty artwork regions and fixture images cannot pass this gate.
- **#224 — Review to delivery and final sign-off** (consolidates #172 and #143). The
  roadmap, combined review/checks and approval/file preparation, and per-format delivery
  receipts are implemented and covered with fake adapters. The release gate remains: Codex and Claude Code/Gemini each
  need generation, reference editing and actual-pixel inspection. Gemini requires
  an explicitly selected image-capable model and server-side credential with
  separately authorized API usage. Missing access is an unfulfilled gate. Record
  sanitized conclusions and limitations; never write credentials or private output
  into issues or this repository.

Provider epic #139 remains open while #152 is unfulfilled. Milestone 2 remains open
until #223 and #224 pass; #171, #172 and #143 are superseded by them. There is no automatic release tag,
public package publication or production upgrade as part of a code merge.

## Acceptance sequence

1. Select the existing assistant/model and an available renderer. Use synthetic
   content in a separate local workspace and pin the selected installed brand.
2. Prepare three source-backed stories and exact image briefs. Check fonts/layout
   before starting any provider. Preparation is not live image acceptance.
3. Authorize and run generation, reference editing and pixel inspection through
   each native provider adapter. Keep request identities and original artifacts;
   reconcile uncertainty rather than blindly retrying.
4. Show actual rendered pages to the owner. Correct failures, repeat affected
   checks and obtain the owner's explicit decision. No assistant grants approval.
5. Exercise exact-revision approval, PNG/PDF/SVG/text downloads and invalidation
   after a source/brand/text/art edit. Keep old approved exports as history.
6. Link sanitized acceptance conclusions to #152/#223/#224, close verified gates
   and the milestone, then follow separately authorized publication instructions.

## Testing the merged app

A normal `marketing-studio restart --all` preserves the existing phone address and
home port, and restarts the studios that were running. It refuses active assistant
jobs without a force flag; do not force away user work. Start Infographic Studio
explicitly with `marketing-studio start --is` if it was not already running.
Use the fresh private link; its return metadata includes the Marketing Studio key.

A source checkout requires an explicitly installed renderer or an explicitly
provided `INFOGRAPHIC_STUDIO_RENDERER` path in the server launch environment.
Prepared supported-platform packages contain a pinned private renderer. Restarting
never installs or updates a renderer, assistant, brand or other studio. Existing
workspaces and shared settings stay in place. If verification fails, preserve the
last good content and return to the previous known application version; rolling
back code does not reverse a Google delivery or a shared repository commit.

See [acceptance](../studios/infographic/docs/acceptance.md),
[provider contracts](../studios/infographic/docs/provider-capabilities.md) and
[installation](installation.md).
