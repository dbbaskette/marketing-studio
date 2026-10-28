# Infographic Studio implementation plan

**Status:** feasibility and foundations implementation in progress; later milestones remain planned.

**Date:** 2026-10-28

**Product specification:** [Infographic Studio specification](infographic-studio-spec.md)

**Roadmap:** [#136: Infographic Studio implementation roadmap](https://github.com/dbbaskette/marketing-studio/issues/136)

**Backlog:** 8 epics, 32 tasks; native parent/sub-issue links and three milestones.

## Outcome and release boundary

Infographic Studio becomes a fourth independently runnable studio under Marketing
Studio. Supply information and a direction, or ask for suggestions; select a
story; produce and revise one clear branded page; approve an exact revision; and
export PNG, one-page PDF, editable SVG, and a text equivalent.

Two configurations are supported: signed-in Codex with its built-in image tool,
or signed-in Claude Code directing an image-capable Gemini model with a
server-side Gemini API key. Claude Code authors an extremely specific visual
description before Gemini renders. Codex records the same explicit art direction.
Image generation and editing are first-release capabilities, not a later add-on.

The first release accepts pasted text, text/Markdown files, and selected CSV
data. It supports directed, suggested, and hybrid story modes; A4, US Letter,
and 1080 × 1350 digital portrait; the selected brand; scoped edits; immutable
history; source fidelity; interruption recovery; and standalone/suite installation.
PDF/Word intake, Google Docs/URL intake, public research, and cross-studio/team
handoffs have their own follow-up epic and do not gate first release. Animation,
a general design editor, automatic publication, press-ready CMYK/bleed, tagged PDF,
and external design-platform synchronization are outside this implementation.

## Architecture and repository boundaries

Keep infographic-specific modules in `studios/infographic/`. Proposed module and
test paths in this plan are implementation targets, not claims that files exist.
Reuse shared infrastructure without importing another studio's pipeline.

| Boundary | Existing integration or proposed implementation |
| --- | --- |
| Native command/server | `studios/infographic/runner/studio.py`, `server.py`, `workspace.py`; shared `studio_core.server` protections |
| Pipeline and project state | Native `engine.py`, `desk_store.py`, `contracts.py`, `validation.py`; compatible `studio_core.drafting` settle/history parts |
| Source/story/art direction | Native `sources.py`, `evidence.py`, `stories.py`, `brand.py`, `image_brief.py`, private prompts |
| Image execution | Native `images/base.py`, `images/codex.py`, `images/gemini.py`, `image_jobs.py`, `image_review.py` |
| Page generation | Native `scene.py`, `layout.py`, `svg.py`, `render.py`, `checks.py`, `exports.py` |
| Editing desk | Native vanilla JavaScript/CSS in `runner/web/`; shared `ui-kit/style.css` and `ui-kit/drafting.js` |
| Marketing Studio | Catalog, launch/lifecycle, CLI, shared setup, settings, status/doctor, optional LAN bridge |
| Distribution | Native installer/skill/guidance, root suite/subset inventories, pinned dependencies, platform bundles, acceptance matrices |

Use Python 3.11 or newer with standard-library application code and no frontend
build step. Any renderer/tool dependency must be explicitly selected, pinned,
packaged, and capability checked. Runtime startup never installs or updates it.

The current shared Codex worker explicitly disables image generation. Do not
remove that protection for all studios. The native image adapter must enable
only its required capability. Verify the actual generation, editing, saved-asset
handoff, and image-inspection surface before writing downstream code against it.
Likewise, the ordinary text-only Claude Code worker cannot be assumed to inspect
images without a verified multimodal handoff.

Marketing Studio's [workflow retirement issue #134](https://github.com/dbbaskette/marketing-studio/issues/134)
moves new work to editing desks. Infographic Studio follows that direction:
story selection and final approval are checkpoints within one desk workflow.
Do not add Step by step/Balanced/Automatic legacy review-level controls, fork
retired pipeline machinery, or require a browser for conversation starts.
Reconcile current main and #134's resulting interfaces at the contract, UI,
and conversation-entry milestones. This roadmap does not change or close #134.

## Saved project and execution contracts

All generated content, original sources, exact prompts, and private job records
live in a separately configured workspace. This application repository contains
code, documentation, and synthetic test definitions only. A project has a stable
identity and versioned source, fact, story-block, scene-element, image-brief,
image-attempt, finding, approval, and export records.

Define these contracts in F03 before provider or UI implementations diverge:

1. **Input basis.** Each derived record pins its source/story/brand/scene/reference
   hashes. Every mutation includes an expected project revision. Every worker
   submission includes the basis it read and its owned attempt ID.
2. **Persistence.** Save atomically under the native workspace/project lock;
   incomplete attempts never replace the last good state. Unknown schema versions,
   invalid references, unsafe paths, and changed ownership are explicit refusals.
3. **Facts.** Literal values retain units, periods, denominators, uncertainty, and
   source locations. Derived values retain operands and deterministic calculations.
   Supplied assertions are distinguished from independent corroboration.
4. **Stories.** A chosen story records its takeaway, reading order, required content,
   exact wording, exclusions, fact references, omissions, and visual form. A
   source/brand/content change invalidates only dependent derived records.
5. **Scene.** Store dimensions, geometry, typography, text, numeric chart encodings,
   connector meanings, source markers, generated-asset placement, and reading order.
   Text/values/chart marks remain editable; embedded generated artwork is raster.
6. **Image brief.** Store a structured brief and the exact provider-ready prompt:
   purpose, canvas, normalized bounds, objects/counts/relationships, focal point,
   spacing, style, brand values, exact text/data ownership, actual reference assets,
   exclusions, acceptance requirements, and edit-preservation instructions.
7. **Provider contract.** Generate/edit/status/cancel/readiness return validated
   studio-owned assets, capability status, request identity when known, and honest
   known/unknown usage. No silent provider switch, separate Codex API-key fallback,
   or automatic repeat of an uncertain billable request.
8. **Checks and approval.** Findings bind exact inputs and scene digests. Only the
   user may approve. Approval binds the checked scene, source/story/brand revisions,
   and export manifests. Restore or any relevant edit creates a new revision and
   never restores approval implicitly.
9. **Exports.** Immutable hashes identify local files for a specific revision.
   Export retry uses the saved approved scene without rerunning generation.
   Unapproved downloads are visibly marked drafts.

The engine implements: capture → extract → propose → story checkpoint → specify
image → generate artwork and compose → inspect/check/repair → page checkpoint →
export. Automatic draft records selection of the recommended story and still
stops for final approval. A job can land only while its input basis remains current.

Before generation, validate image-brief coverage, exact content, region bounds,
and compositor reservations. The prompt must stand alone without the conversation,
repository, inaccessible paths, or unrelated source documents. After generation,
the directing assistant inspects the actual image and composed page against that
brief. Correction instructions name the observed mismatch, exact change, prior
asset, and preserved elements. No image-inspection capability means an incomplete
visual check and manual review, not a passed check.

Image and layout corrections share the maximum of two automatic repair attempts.
No stage can open another unbounded correction loop. User-requested subsequent
revisions are new, explicit work. A timeout with uncertain provider outcome is
saved for explicit recovery; reconnect must not submit the same image again.

## Security, settings, and lifecycle

- Shared preferences use the existing `studios-config.json` and adjacent lock.
  Preserve unrelated leaves; refuse conflicts from outdated forms. Image/page
  defaults are native non-secret preferences, not a second shared authority.
- Read `GEMINI_API_KEY` server-side only. Do not write it into settings, project
  files, prompts, browser storage/responses, CLI arguments, URLs, archives, or logs.
  Exclude it from assistant and renderer child environments. Document how terminal
  and desktop launch inherit the configured environment; never pretend a GUI
  launcher inherited a key that it did not.
- A present key or executable is a local prerequisite, not a successful live
  generation check. Separate configured, locally available, live-verified, and
  unavailable states. Live checks that generate content or incur usage require
  an explicit action. Opening setup/status/preview starts no paid provider work.
- Supplied-only mode does not mean local-only processing. Disclose selected
  assistant/image providers before jobs; send only necessary inputs. No implicit
  source fetch, web search, image grounding, publication, or team sharing.
- Use the existing loopback/session/Host/Origin protections. Bound requests and
  assets; reject traversal, unsafe links, executable SVG, arbitrary file access,
  and external resources in exported SVG.
- Explicit setup or launch may initialize an unconfigured workspace. Never move
  an existing one, overwrite unrelated settings, or auto-install/update studios.
  Process cancellation and shutdown signal only verified owned jobs.
- Cancellation may not stop a remote request already in flight; it must prevent
  adoption and expose that uncertainty. Keep original assets, previous previews,
  approvals, and delivered files intact.

## Delivery sequence and exit gates

Use coherent reviewed increments, targeted verification at each milestone,
and the full relevant suite once on final integrated source. Dependencies below
are implementation prerequisites, not a promise that every issue in one epic
must finish before another epic can begin.

| Gate | Scope | Exit requirement |
| --- | --- | --- |
| G0: feasibility and foundations | E1 / F01–F04 | Real execution design for both providers and image inspection; selected renderer; versioned contracts; isolated standalone skeleton |
| G1: source-to-story | E2 / S01–S04 | Supported input capture and evidence; all three story modes; pinned brand and content requirements |
| G2: art direction and images | E3 / I01–I05 | Extremely specific briefs; both adapters; safe attempts; actual image inspection and bounded corrections |
| G3: page and exports | E4 / R01–R04 | Faithful supported visual forms; checked single-page scene; exact PNG/PDF/SVG/text delivery |
| G4: usable resilient desk | E5 / W01–W04 | Resumable workflow, story/page checkpoints, scoped edits, history, and exact-revision approval |
| G5: integrated installation | E6 / D01–D04 | Shared settings/launch, browser-free conversation entry, source-independent native/suite/subset bundles |
| G6: release readiness | E7 / Q01–Q03 | Offline/native/visual suites, separately recorded provider acceptance, final documentation and release evidence |
| Later | E8 / L01–L04 | Explicitly scheduled extensions; no first-release dependency |

The first implementation work is F01 and F02, which are independent investigations.
F03 waits for both; F04 establishes the native boundary. Source/story and provider
adapter work can then proceed on stable contracts. R02 must exist before I05 can
inspect a composed page. W01 integrates the tested story, provider, composition,
check, and export components; UI and distribution follow. Existing shared code
changes get root/native regressions immediately, not only at G6.

No calendar dates, assignees, or spend commitments are inferred. The feasibility
gate resolves the largest unknowns before estimates are made. Large implementation
issues can be split into smaller child work before coding; preserve acceptance
criteria, dependency references, and epic ownership.

## Verification and definition of done

Every task below includes its own meaningful checks; do not defer ordinary
tests until Q01. Tests run with synthetic content and disposable HOME, settings,
workspaces, Git identities, data folders, and owned processes. Inject provider
transports and image results. Never inspect personal keys, start real provider
jobs, update real installations, or access team content during automated checking.

| Coverage | Required evidence |
| --- | --- |
| Contracts and persistence | Validation, unknown schema refusal, atomic writes, conflicts, pin changes, corrupt attempts |
| Source/evidence | Exact captures, CSV ambiguity, source locations, arithmetic, dates/units, contradictions, no implicit fetch |
| Image generation | Both adapters, missing capabilities, auth/quota/refusal, malformed assets, secret redaction, timeout/cancel/reconnect |
| Art direction and inspection | Self-contained precise briefs, brand/content fidelity, reserved regions, actual-image mismatch handling, missing inspection |
| Composition and exports | All forms/presets, text floors, overflow, one-page PDF, exact pixels, editable element fidelity, accessible text |
| Workflow | Three direction modes, automatic draft, final approval, focused edits, restore, dependency invalidation, last-good retention |
| Native integration | Fourth-studio setup/launch/CLI, standalone reuse, ownership, optional LAN boundary, unchanged existing studios |
| Packaging | Deterministic full/subset archives, selected dependencies, source-independent install, rollback/content preservation |
| UI | Desktop/phone, light/dark, reduced transparency/motion, keyboard/touch, actual-size rendered inspection |

Use the repository's existing commands, extending them for the fourth studio:

```sh
python3 -m unittest discover -s studios/infographic/tests -v
python3 studios/infographic/skills/infographic-studio/scripts/validate_package.py
python3 -m unittest discover -s tests -v
bash scripts/ci/tart-macos.sh --dry-run
bash scripts/ci/tart-macos.sh
```

The first two commands are proposed native entry points to add; they are not
available yet. The shared Tart entry point runs the root/native suites and
acceptance checks. Packaging acceptance must inspect actual built source-independent
platform bundles using the existing bundle-acceptance workflow. Do not publish
untested platforms based on cross-platform assembly alone.

A task closes when its implementation and relevant docs are merged, its acceptance
criteria and targeted tests pass, and its issue links to the evidence/change.
An epic closes when its child work and exit gate pass. First-release readiness
requires E1–E7; E8 is explicitly deferred. Actual live provider generation/edit/
inspection acceptance is a separate manual activity requested before execution,
recording sanitized conclusions without keys or machine-specific operational logs.
The initial backlog creation performed no application implementation or provider
verification. The feasibility and foundations milestone now contains native
contracts, capability definitions, an isolated skeleton, and a rendering spike;
later pipeline milestones remain planned. Live provider verification, production
publication, and real installation upgrades have not been performed.

## Risks and decisions to resolve

| Decision or risk | Owner task | Required resolution |
| --- | --- | --- |
| Codex image tool under confined native execution | F01 / I03 | Prove usable generation/editing without broadly enabling tools or requiring another API key |
| Claude Code seeing the actual returned image | F01 / I05 | Verify multimodal handoff; unavailable inspection must require manual review |
| Renderer, exact fonts, and portable exports | F02 / R02 / D04 | Select dependency, minimum versions, supported platforms, licenses, and pinned packaging |
| Dense material cannot fit one page | S03 / R01 | Preserve required content and type floors; ask for prioritization rather than silently omit or shrink |
| Gemini model access/credential in desktop launch | I02 / D01 | Distinct capability outcomes, explicit environment configuration, no secret persistence |
| Image retries create duplicate usage | I04 | Persist request uncertainty and expose explicit recovery |
| Main moves during workflow retirement | F03 / W01 / D03 | Reconcile #134's interfaces, keep desk-first new work, and avoid legacy review controls |
| Source and brand updates invalidate a draft | W04 | Dependency-aware recalculation and explicit new approval |
| Generated artwork cannot be edited as vector paths | R02 / R04 | Preserve precise content in SVG and document raster artwork limitations |

## Epic and issue index

GitHub issue state is authoritative for progress. The first milestone is in
implementation; issues close only after their changes merge. The roadmap has native child epics, and each epic has
native child tasks. Linked task checklists mirror these relationships for navigation.

Milestones: [Feasibility and foundations](https://github.com/dbbaskette/marketing-studio/milestone/1),
[first release](https://github.com/dbbaskette/marketing-studio/milestone/2), and [follow-up capabilities](https://github.com/dbbaskette/marketing-studio/milestone/3).
The first release requires both the feasibility and first-release milestones.
The roadmap can remain open to track follow-up work after the first release.

| Epic | GitHub issue | Tasks | Delivery |
| --- | --- | --- | --- |
| E1: foundations and feasibility | [#137](https://github.com/dbbaskette/marketing-studio/issues/137) | 4 | Feasibility |
| E2: source evidence and story direction | [#138](https://github.com/dbbaskette/marketing-studio/issues/138) | 4 | First release |
| E3: precise art direction and image providers | [#139](https://github.com/dbbaskette/marketing-studio/issues/139) | 5 | First release |
| E4: single-page composition and exports | [#140](https://github.com/dbbaskette/marketing-studio/issues/140) | 4 | First release |
| E5: editing desk and revision workflow | [#141](https://github.com/dbbaskette/marketing-studio/issues/141) | 4 | First release |
| E6: Marketing Studio integration and distribution | [#142](https://github.com/dbbaskette/marketing-studio/issues/142) | 4 | First release |
| E7: verification and first-release readiness | [#143](https://github.com/dbbaskette/marketing-studio/issues/143) | 3 | First release |
| E8: follow-up sources, research, and handoffs | [#144](https://github.com/dbbaskette/marketing-studio/issues/144) | 4 | Follow-up |

Start with [F01: provider capability investigation](https://github.com/dbbaskette/marketing-studio/issues/145) and
[F02: rendering investigation](https://github.com/dbbaskette/marketing-studio/issues/146); neither has an implementation prerequisite.

### E1: foundations and feasibility

**Epic:** [#137](https://github.com/dbbaskette/marketing-studio/issues/137) · **Roadmap:** [#136](https://github.com/dbbaskette/marketing-studio/issues/136)

Prove both supported image-provider paths and one-page rendering, then establish versioned contracts and an independently runnable studio boundary.

**Exit gate:** The Codex and Claude Code with Gemini paths have an executable design, image inspection has a defined capability, the renderer is selected, and a disposable standalone skeleton preserves existing settings and workspaces.

#### F01: prove Codex and Claude Code with Gemini image capabilities

**Issue:** [#145](https://github.com/dbbaskette/marketing-studio/issues/145) · **Epic:** [#137](https://github.com/dbbaskette/marketing-studio/issues/137)

**Prerequisites:** None; start here.

**Delivery:** Feasibility and foundations

**Paths:** `core/studio_core/shared_runner/agents.py`, `studios/infographic/docs/provider-capabilities.md`, `studios/infographic/tests/test_provider_capabilities.py`

Work:

- Document the actual installed execution surfaces for Codex generation/editing and Claude Code directing Gemini, including access to returned images for inspection.
- Determine the minimum supported runtime and image-model capabilities without assuming that CLI presence, model naming, or a present key proves availability.
- Design scoped Codex image access while preserving CODEX_OFF and confinement for existing studios; identify how Claude Code receives returned images for visual inspection.
- Record manual acceptance instructions and sanitized capability conclusions; do not start provider work as part of this planning issue or automated checks.

Acceptance criteria:

- [ ] Both supported routes have a concrete generate/edit/inspect handoff and non-secret capability report.
- [ ] Unavailable image tools, absent inspection, missing sign-in, and missing Gemini credentials have distinct outcomes.
- [ ] No separate image API key is required for the supported Codex built-in route; no silent API-key fallback or provider switch.
- [ ] Any unsupported runtime surface is reported as a feasibility blocker before downstream production claims.

**Verification:** Stub CLI/tool catalogs and adapter transcripts; assert existing studios still disable image generation. Real generation requires a separately requested manual run using synthetic inputs.

#### F02: select and prove the single-page export renderer

**Issue:** [#146](https://github.com/dbbaskette/marketing-studio/issues/146) · **Epic:** [#137](https://github.com/dbbaskette/marketing-studio/issues/137)

**Prerequisites:** None; start here.

**Delivery:** Feasibility and foundations

**Paths:** `studios/infographic/runner/render.py`, `studios/infographic/docs/rendering-decision.md`, `pins/companions.json`, `pins/runtimes.json`

Work:

- Evaluate a reusable installed renderer or pinned companion using synthetic comparison, process, and conceptual scenes.
- Prove font measurement, wrapping, embedded raster assets, SVG fidelity, PNG sizing, and true one-page PDF output.
- Record dependency/version, platform support, font licensing limits, packaging strategy, and missing-capability diagnostics.
- Keep application Python standard-library-only and avoid a frontend build step or runtime downloads.

Acceptance criteria:

- [ ] A4 and US Letter portrait render at intended physical sizes; 1080 × 1350 digital renders at exact pixels.
- [ ] Overflow, missing fonts, and missing assets are detected rather than hidden by scaling or extra PDF pages.
- [ ] SVG text and chart geometry survive export; raster artwork is explicitly distinguished from editable vectors.
- [ ] The selected dependency can be pinned and shipped in a source-independent native bundle; unsupported platforms are named.

**Verification:** Local renderer-only smoke checks with disposable synthetic scenes and open-licensed or system fonts; no assistant or image-provider calls.

#### F03: define versioned project, scene, image-brief, and adapter contracts

**Issue:** [#147](https://github.com/dbbaskette/marketing-studio/issues/147) · **Epic:** [#137](https://github.com/dbbaskette/marketing-studio/issues/137)

**Prerequisites:** [F01 / #145](https://github.com/dbbaskette/marketing-studio/issues/145), [F02 / #146](https://github.com/dbbaskette/marketing-studio/issues/146)

**Delivery:** Feasibility and foundations

**Paths:** `studios/infographic/runner/contracts.py`, `studios/infographic/runner/validation.py`, `studios/infographic/docs/contracts.md`, `studios/infographic/tests/test_contracts.py`

Work:

- Specify stable IDs and schemas for brief, sources, facts/calculations, story blocks, scene elements, image briefs, attempts, findings, approvals, and export manifests.
- Define provider generate/edit/status/cancel/readiness results including unknown cost, unknown timeout outcome, inspection capability, and asset ownership.
- Define expected-revision mutations, input digests, atomic save boundaries, stage invalidation, maximum input/asset sizes, and schema compatibility refusal.
- Document story selection and final approval as desk checkpoints; reconcile with workflow retirement issue #134 without adding legacy review-level controls.

Acceptance criteria:

- [ ] Schema validation rejects invalid references, malformed dimensions, unsupported versions, and conflicting units or ownership.
- [ ] A mutation and a worker result carry the exact revision/input basis needed for safe application.
- [ ] Approvals bind source, story, brand, scene, checks, and export identities; updates cannot inherit approval silently.
- [ ] Image briefs account for precise composition and separate artwork instructions from compositor-owned text and chart marks.

**Verification:** Standard-library validation tests with synthetic complete records, corrupt records, unknown schema versions, and changed dependency digests.

#### F04: create the independently runnable studio skeleton and secure workspace

**Issue:** [#148](https://github.com/dbbaskette/marketing-studio/issues/148) · **Epic:** [#137](https://github.com/dbbaskette/marketing-studio/issues/137)

**Prerequisites:** [F03 / #147](https://github.com/dbbaskette/marketing-studio/issues/147)

**Delivery:** Feasibility and foundations

**Paths:** `studios/infographic/runner/studio.py`, `studios/infographic/runner/workspace.py`, `studios/infographic/runner/server.py`, `studios/infographic/tests/helpers.py`, `core/studio_core/server.py`, `core/studio_core/workspace_setup.py`

Work:

- Create native CLI/server entry points, a local data directory override, project locking, and a workspace adapter using shared infrastructure.
- Provide offline help, status, draft storage, and authenticated project APIs with bounded reads and writes.
- Initialize an unconfigured workspace only on explicit setup or launch and preserve any existing configured workspace.
- Use suite-owned core/UI links in source and prepare for ordinary-file materialization in installed bundles.

Acceptance criteria:

- [ ] The skeleton starts without Marketing Studio and without starting an assistant, fetching sources, or installing software.
- [ ] Host/Origin/session checks, path containment, symlink refusal, request size limits, and protected asset reads follow shared server rules.
- [ ] Conflicting revisions and concurrent writers are refused without partial saves.
- [ ] Tests isolate HOME, shared settings, Git identity, workspace, data directory, and owned processes.

**Verification:** Native CLI/unit and real disposable loopback-server tests; snapshot a disposable existing workspace before and after setup/launch.

### E2: source evidence and story direction

**Epic:** [#138](https://github.com/dbbaskette/marketing-studio/issues/138) · **Roadmap:** [#136](https://github.com/dbbaskette/marketing-studio/issues/136)

Turn supplied text, Markdown, and CSV into traceable facts and useful directed, suggested, or hybrid visual stories.

**Exit gate:** All three direction modes preserve required content, numerical comparisons retain their context, conceptual stories need no invented measurements, and the chosen brand is captured.

#### S01: capture pasted text, Markdown, and CSV sources

**Issue:** [#149](https://github.com/dbbaskette/marketing-studio/issues/149) · **Epic:** [#138](https://github.com/dbbaskette/marketing-studio/issues/138)

**Prerequisites:** [F04 / #148](https://github.com/dbbaskette/marketing-studio/issues/148)

**Delivery:** First release

**Paths:** `studios/infographic/runner/sources.py`, `studios/infographic/runner/api.py`, `studios/infographic/tests/test_sources.py`

Work:

- Capture immutable source bytes, normalized text, hashes, source locations, and readiness limits.
- Add CSV preview and row/column selection with explicit numeric types, missing values, dates, and units.
- Reject unsupported formats before starting a job and surface unreadable or truncated source coverage.
- Keep pasted URLs as references; supplied-only mode must never fetch, search, or silently share uploads.

Acceptance criteria:

- [ ] Pasted text and supported files remain traceable to exact captured revisions.
- [ ] CSV selection is confirmed before use and does not silently coerce ambiguous numbers or omit selected rows.
- [ ] Invalid encoding, oversized files, traversal paths, and unsupported types produce actionable errors.
- [ ] Source updates invalidate dependent facts and previews while retaining previous revisions.

**Verification:** Temporary text/Markdown/CSV fixtures covering ambiguous units, Unicode, malformed CSV, limits, and no-network assertions.

#### S02: extract source-backed ideas, facts, and calculations

**Issue:** [#153](https://github.com/dbbaskette/marketing-studio/issues/153) · **Epic:** [#138](https://github.com/dbbaskette/marketing-studio/issues/138)

**Prerequisites:** [S01 / #149](https://github.com/dbbaskette/marketing-studio/issues/149), [F03 / #147](https://github.com/dbbaskette/marketing-studio/issues/147)

**Delivery:** First release

**Paths:** `studios/infographic/runner/evidence.py`, `studios/infographic/runner/prompts/evidence.md`, `studios/infographic/tests/test_evidence.py`

Work:

- Extract qualitative ideas and quantitative facts with exact source locations and stable IDs.
- Retain units, dates, denominators, conditions, uncertainty, and supplied-versus-corroborated status.
- Store derived values as explicit calculations over source operands and validate them deterministically.
- Surface contradictions and missing context without inventing a resolution or treating the user's goal as evidence.

Acceptance criteria:

- [ ] Every factual claim used downstream resolves to a captured source or reproducible calculation.
- [ ] Conflicting values and incomparable periods or units remain visible and block misleading comparisons.
- [ ] Conceptual source material yields usable ideas without manufactured metrics.
- [ ] Changed sources invalidate dependent facts and calculations.

**Verification:** Scripted extraction outputs plus deterministic source-location, arithmetic, unit, contradiction, and invalidation checks.

#### S03: implement directed, suggested, and hybrid story selection

**Issue:** [#156](https://github.com/dbbaskette/marketing-studio/issues/156) · **Epic:** [#138](https://github.com/dbbaskette/marketing-studio/issues/138)

**Prerequisites:** [S02 / #153](https://github.com/dbbaskette/marketing-studio/issues/153)

**Delivery:** First release

**Paths:** `studios/infographic/runner/stories.py`, `studios/infographic/runner/prompts/stories.md`, `studios/infographic/tests/test_stories.py`

Work:

- Implement I know what to show, Suggest the story, and Build on my ideas as distinct input modes.
- Produce up to three meaningfully different explanations, with takeaway, visual plan, source-backed blocks, thumbnail plan, and rationale.
- Preserve exact wording, required content, exclusions, source qualifications, and recorded omissions.
- Enforce content-fit planning and ask for prioritization when must-show material cannot fit; do not fill a quota of suggestions.

Acceptance criteria:

- [ ] Directed mode proposes one faithful plan; hybrid suggestions retain required ideas.
- [ ] Suggestion alternatives differ in explanation or structure rather than palette alone.
- [ ] One useful option is acceptable; factual gaps and proposed omissions are visible before generation.
- [ ] The chosen story has stable block/fact references and a versioned selection checkpoint.

**Verification:** Scripted qualitative, numeric, sparse-source, contradiction, overfull, and exact-wording cases for all three modes.

#### S04: capture brand guidance and visual constraints

**Issue:** [#150](https://github.com/dbbaskette/marketing-studio/issues/150) · **Epic:** [#138](https://github.com/dbbaskette/marketing-studio/issues/138)

**Prerequisites:** [F04 / #148](https://github.com/dbbaskette/marketing-studio/issues/148)

**Delivery:** First release

**Paths:** `studios/infographic/runner/brand.py`, `core/studio_core/brand_catalog.py`, `core/studio_core/brand_guidance.py`, `studios/infographic/tests/test_brand.py`

Work:

- Resolve the configured brand and variant into a pinned snapshot of colors, fonts, permitted assets, and applicable visual guidance.
- Reuse compatible brand discovery without requiring slide-only templates or hard-coding an organization.
- Distinguish a missing brand contract, unavailable font, missing reference asset, and unsupported capability.
- Record redistribution/embedding limits and constrain typography floors and image prompts accordingly.

Acceptance criteria:

- [ ] Changing the current brand default cannot silently alter an in-progress approved story or scene.
- [ ] Image briefs receive resolved brand constraints and actual permitted reference assets.
- [ ] No organization or machine-specific brand path is embedded in product defaults.
- [ ] Missing requirements remain actionable and never trigger automatic brand installation or updates.

**Verification:** Synthetic brand contracts/variants and temporary assets; missing font, changed revision, unsupported guidance, and path-containment checks.

### E3: precise art direction and image providers

**Epic:** [#139](https://github.com/dbbaskette/marketing-studio/issues/139) · **Roadmap:** [#136](https://github.com/dbbaskette/marketing-studio/issues/136)

Make Claude Code or Codex author a precise image brief, generate and edit through the selected image provider, and inspect the actual result.

**Exit gate:** Both image adapters conform to the same job contract; detailed prompts, scoped access, secret handling, bounded correction, and image-result inspection work end to end with stand-ins.

#### I01: author and validate extremely specific image briefs

**Issue:** [#157](https://github.com/dbbaskette/marketing-studio/issues/157) · **Epic:** [#139](https://github.com/dbbaskette/marketing-studio/issues/139)

**Prerequisites:** [S03 / #156](https://github.com/dbbaskette/marketing-studio/issues/156), [S04 / #150](https://github.com/dbbaskette/marketing-studio/issues/150), [F03 / #147](https://github.com/dbbaskette/marketing-studio/issues/147)

**Delivery:** First release

**Paths:** `studios/infographic/runner/image_brief.py`, `studios/infographic/runner/prompts/image-brief.md`, `studios/infographic/tests/test_image_brief.py`

Work:

- Have Claude Code act as art director and write a self-contained provider-ready description; Codex records the same explicit visual intent.
- Specify audience/takeaway, canvas, normalized regions, every object and relationship, scale, spacing, reading order, style, brand values, exact text/data ownership, references, exclusions, and acceptance requirements.
- Save image-brief.json and the exact sent prompt per attempt, bound to story/scene/brand/reference hashes.
- Resolve design ambiguities before submitting; forbid generic prompts, inaccessible local references, unrelated sources, and secret interpolation.

Acceptance criteria:

- [ ] The provider can understand the requested image without the conversation or repository.
- [ ] Required objects and relationships map to approved story blocks; labels and numbers match locked content.
- [ ] Artwork prompts explicitly reserve compositor-owned regions and prohibit unwanted text or chart marks.
- [ ] Edits specify the exact requested change and what must remain unchanged; changed pinned inputs invalidate the brief.

**Verification:** Schema and semantic fixture checks for missing composition details, changed facts, conflicting bounds, exact wording, unsupported references, and deliberate secret sentinels.

#### I02: implement the Gemini image-generation and editing adapter

**Issue:** [#151](https://github.com/dbbaskette/marketing-studio/issues/151) · **Epic:** [#139](https://github.com/dbbaskette/marketing-studio/issues/139)

**Prerequisites:** [F01 / #145](https://github.com/dbbaskette/marketing-studio/issues/145), [F04 / #148](https://github.com/dbbaskette/marketing-studio/issues/148), [F03 / #147](https://github.com/dbbaskette/marketing-studio/issues/147)

**Delivery:** First release

**Paths:** `studios/infographic/runner/images/gemini.py`, `studios/infographic/runner/images/base.py`, `studios/infographic/tests/test_gemini_images.py`

Work:

- Use server-side standard-library HTTPS/JSON to call the selected image-capable Gemini model for generation and reference-image editing.
- Read GEMINI_API_KEY only in the adapter; pass neither key nor unrestricted environment to Claude Code or browser clients.
- Normalize binary assets, request IDs, reported usage, refusals, unsupported capability, quota, authentication, and timeout outcomes.
- Bound response size and request duration, validate media, disable unrequested search/grounding, and redact provider errors.

Acceptance criteria:

- [ ] Generation and edits return studio-owned validated files through the shared image contract.
- [ ] Missing/invalid key, inaccessible image model, quota refusal, and provider failure are distinct outcomes.
- [ ] No key appears in settings, prompts, artifacts, CLI arguments, URLs, logs, or API responses.
- [ ] An unknown timeout outcome is preserved without automatic duplicate billable submissions.

**Verification:** Injected HTTP transport with synthetic success/error/binary responses; no live key or network needed. Verify secret sentinels across all outputs.

#### I03: implement scoped Codex built-in image generation and editing

**Issue:** [#152](https://github.com/dbbaskette/marketing-studio/issues/152) · **Epic:** [#139](https://github.com/dbbaskette/marketing-studio/issues/139)

**Prerequisites:** [F01 / #145](https://github.com/dbbaskette/marketing-studio/issues/145), [F04 / #148](https://github.com/dbbaskette/marketing-studio/issues/148), [F03 / #147](https://github.com/dbbaskette/marketing-studio/issues/147)

**Delivery:** First release

**Paths:** `studios/infographic/runner/images/codex.py`, `core/studio_core/shared_runner/agents.py`, `studios/infographic/tests/test_codex_images.py`, `tests/test_shared_runner.py`

Work:

- Implement the proven Codex built-in image-tool route with narrowly scoped image and reference-asset access.
- Use existing Codex sign-in and image capability rather than introducing a separate OpenAI API-key requirement or silent fallback.
- Capture generated assets and editing results as studio-owned files with capability/refusal/usage outcomes.
- Preserve all existing studios' disabled image tool and broader worker confinement.

Acceptance criteria:

- [ ] Both generate and reference-guided edit use the real supported tool surface defined by the feasibility result.
- [ ] The adapter fails clearly when installed Codex cannot expose the image tool in the selected execution mode.
- [ ] No unrelated plugin, browser, shell, or multi-agent capability is enabled as a side effect.
- [ ] Results conform to the same provider-neutral image contract as Gemini.

**Verification:** Stub runtime/tool event streams for success, absent image tool, auth, quota, malformed asset, and edit results; existing shared-runner command regression tests.

#### I04: persist image attempts, cancellation, limits, and safe result adoption

**Issue:** [#154](https://github.com/dbbaskette/marketing-studio/issues/154) · **Epic:** [#139](https://github.com/dbbaskette/marketing-studio/issues/139)

**Prerequisites:** [I02 / #151](https://github.com/dbbaskette/marketing-studio/issues/151), [I03 / #152](https://github.com/dbbaskette/marketing-studio/issues/152)

**Delivery:** First release

**Paths:** `studios/infographic/runner/image_jobs.py`, `studios/infographic/runner/jobs.py`, `studios/infographic/tests/test_image_jobs.py`

Work:

- Persist attempt IDs, request/input hashes, edit parents, provider request IDs, returned assets, and known/unknown usage.
- Apply existing applicable job limits plus the two-attempt automatic repair ceiling; never manufacture costs.
- Prevent automatic resubmission of an uncertain in-flight result; expose explicit retry and preserve previous assets.
- Cancel only owned jobs, reject stale result adoption, and isolate generated assets by project/revision/attempt.

Acceptance criteria:

- [ ] Restart and reconnect recover known state without duplicate generation.
- [ ] Late results cannot replace a newer scene or attach to another project.
- [ ] Cancellation prevents adoption even if remote provider cancellation is unavailable.
- [ ] Opening or inspecting a project does not call a provider; changing provider requires an explicit action.

**Verification:** Scripted provider plus disposable processes covering timeout, partial response, restart, concurrent revisions, cancellation, quota, and no-slot/no-process leaks.

#### I05: inspect returned images and issue specific correction instructions

**Issue:** [#160](https://github.com/dbbaskette/marketing-studio/issues/160) · **Epic:** [#139](https://github.com/dbbaskette/marketing-studio/issues/139)

**Prerequisites:** [I01 / #157](https://github.com/dbbaskette/marketing-studio/issues/157), [I04 / #154](https://github.com/dbbaskette/marketing-studio/issues/154), [R02 / #159](https://github.com/dbbaskette/marketing-studio/issues/159)

**Delivery:** First release

**Paths:** `studios/infographic/runner/image_review.py`, `studios/infographic/runner/prompts/image-review.md`, `studios/infographic/tests/test_image_review.py`

Work:

- Expose the actual returned asset and composed page to the directing assistant using the verified image-inspection surface.
- Compare required objects, connections, reading order, brand, exclusions, and any visible words against the saved image brief.
- Create an edit request naming observed mismatches, exact changes, and preserved elements, referencing the prior asset.
- Share the global two-attempt repair budget and leave unresolved findings visible; unavailable inspection requires manual review.

Acceptance criteria:

- [ ] A successful provider response cannot by itself pass the visual check.
- [ ] Missing required objects or reversed relationships produce specific findings tied to scene/brief elements.
- [ ] Unavailable or incomplete image inspection never produces a passed visual-verification record.
- [ ] Corrections preserve the original image, brief, request history, and unaffected locked content.

**Verification:** Scripted inspection outcomes referencing synthetic known image fixtures; tests for mismatch specificity, unchanged-region requirements, unavailable capability, and repair exhaustion.

### E4: single-page composition and exports

**Epic:** [#140](https://github.com/dbbaskette/marketing-studio/issues/140) · **Roadmap:** [#136](https://github.com/dbbaskette/marketing-studio/issues/136)

Combine generated artwork with accurate editable text, charts, and connectors, then export a legible single page.

**Exit gate:** All required visual relationships fit the three presets, blocking findings prevent final approval, and PNG, PDF, SVG, and text exports retain revision and source fidelity.

#### R01: build single-page scene planning for the supported visual forms

**Issue:** [#158](https://github.com/dbbaskette/marketing-studio/issues/158) · **Epic:** [#140](https://github.com/dbbaskette/marketing-studio/issues/140)

**Prerequisites:** [S03 / #156](https://github.com/dbbaskette/marketing-studio/issues/156), [S04 / #150](https://github.com/dbbaskette/marketing-studio/issues/150), [F03 / #147](https://github.com/dbbaskette/marketing-studio/issues/147)

**Delivery:** First release

**Paths:** `studios/infographic/runner/layout.py`, `studios/infographic/runner/scene.py`, `studios/infographic/tests/test_layout.py`

Work:

- Plan comparison, process, timeline, key-number, part-to-whole, and conceptual/system visual forms with stable scene element IDs.
- Use one dominant explanation, clear reading order, evidence references, accessible labels, and artwork reservations.
- Support A4, US Letter, and digital portrait with the specified type floors and content-budget rules.
- Keep numeric encodings faithful to units/baselines and conceptual arrows distinct from measured quantities.

Acceptance criteria:

- [ ] Each visual relationship has a deterministic synthetic layout case, including a conceptual page with no metrics.
- [ ] Required content cannot disappear or shrink below floors to force a fit.
- [ ] Selected dimensions, safe bounds, source footer, and art regions are explicit in the scene.
- [ ] Unsupported or overfull scenes produce actionable findings before rendering.

**Verification:** Scene geometry and semantic tests for all presets/forms, long labels, zero/negative values, missing dates, crowded content, and mixed units.

#### R02: render safe editable SVG with artwork, labels, and charts

**Issue:** [#159](https://github.com/dbbaskette/marketing-studio/issues/159) · **Epic:** [#140](https://github.com/dbbaskette/marketing-studio/issues/140)

**Prerequisites:** [R01 / #158](https://github.com/dbbaskette/marketing-studio/issues/158), [F02 / #146](https://github.com/dbbaskette/marketing-studio/issues/146)

**Delivery:** First release

**Paths:** `studios/infographic/runner/svg.py`, `studios/infographic/runner/render.py`, `studios/infographic/tests/test_svg.py`

Work:

- Compose scene elements into SVG using the standard library; preserve editable text, chart marks, connectors, and source markers.
- Embed validated generated raster artwork while retaining distinct compositor-owned exact text and numeric geometry.
- Use verified font metrics, wrapping, clipping bounds, asset licensing constraints, and deterministic rendering input.
- Disallow executable SVG, external resource fetches, unexpected file references, and unsupported image types.

Acceptance criteria:

- [ ] Changing a label or value need not regenerate unrelated artwork.
- [ ] Text, numbers, and connectors correspond to stable scene elements and source-backed facts.
- [ ] Embedded raster images are never described as editable vector illustrations.
- [ ] The SVG renders with no external network requests, scripts, or missing required assets.

**Verification:** Parse exported XML, inspect scene-to-SVG geometry/text mappings, and render local synthetic cases through the selected renderer; include malicious/oversized asset cases.

#### R03: enforce content, numerical, layout, accessibility, and brand checks

**Issue:** [#161](https://github.com/dbbaskette/marketing-studio/issues/161) · **Epic:** [#140](https://github.com/dbbaskette/marketing-studio/issues/140)

**Prerequisites:** [R02 / #159](https://github.com/dbbaskette/marketing-studio/issues/159), [S02 / #153](https://github.com/dbbaskette/marketing-studio/issues/153)

**Delivery:** First release

**Paths:** `studios/infographic/runner/checks.py`, `studios/infographic/runner/repair.py`, `studios/infographic/tests/test_checks.py`

Work:

- Check required ideas/wording, fact references/calculations, chart values, units, conditions, geometry, fonts, contrast, reading order, and brand constraints.
- Combine deterministic findings with separately recorded image-review findings without treating one as a substitute for the other.
- Separate blocking invalidity from acknowledgeable editorial advice; bind checks to exact inputs and scene digests.
- Apply bounded fixes without changing locked wording or silently dropping content; preserve unresolved findings.

Acceptance criteria:

- [ ] Omitted requirements, contradictory/untraceable claims, invalid geometry, and failed exports block final approval.
- [ ] Type floors and exactly-one-page rules hold at actual output size.
- [ ] Changing any checked dependency invalidates the relevant result.
- [ ] Automatic fixes and image corrections share two repair attempts, with no nested unlimited retry loop.

**Verification:** Purposeful synthetic failures for required text, arithmetic, data encodings, overlapping labels, missing fonts, contrast, changed digest, and repair limits.

#### R04: export PNG, one-page PDF, editable SVG, and accessible text

**Issue:** [#162](https://github.com/dbbaskette/marketing-studio/issues/162) · **Epic:** [#140](https://github.com/dbbaskette/marketing-studio/issues/140)

**Prerequisites:** [R02 / #159](https://github.com/dbbaskette/marketing-studio/issues/159), [R03 / #161](https://github.com/dbbaskette/marketing-studio/issues/161)

**Delivery:** First release

**Paths:** `studios/infographic/runner/exports.py`, `studios/infographic/tests/test_exports.py`, `studios/infographic/docs/exports.md`

Work:

- Create exact-preset PNG, a true one-page RGB PDF, editable SVG, and a reading-order text companion with diagrams, chart data, and sources.
- Use 300 dpi for print PNG and exact 1080 × 1350 pixels for digital; verify selected physical PDF dimensions.
- Record immutable export hashes, scene/source/brand/check identities, font caveats, and any draft marker.
- Retry export from a saved approved scene without rerunning assistants; keep all delivery local unless the user chooses a destination.

Acceptance criteria:

- [ ] Files match the approved revision and intended dimensions; PDF contains exactly one page.
- [ ] Text remains text where supported; missing font portability or embedding rights are disclosed.
- [ ] Public-facing references contain no credentials, session keys, private operational records, or machine-local paths.
- [ ] Failed exports preserve approval and scene state for retry; unapproved downloads are visibly marked drafts.

**Verification:** Inspect PNG headers and SVG XML; use renderer companion PDF inspection for page count/boxes/text; compare export manifests and test partial-failure recovery with synthetic scenes.

### E5: editing desk and revision workflow

**Epic:** [#141](https://github.com/dbbaskette/marketing-studio/issues/141) · **Roadmap:** [#136](https://github.com/dbbaskette/marketing-studio/issues/136)

Deliver a resilient editing desk with story selection, page review, focused changes, history, and exact-revision approval.

**Exit gate:** The three direction modes reach the same desk, automatic drafting still stops at final approval, and interrupted or outdated work cannot replace the last good page.

#### W01: orchestrate the resumable desk pipeline and exact-revision approval

**Issue:** [#163](https://github.com/dbbaskette/marketing-studio/issues/163) · **Epic:** [#141](https://github.com/dbbaskette/marketing-studio/issues/141)

**Prerequisites:** [F04 / #148](https://github.com/dbbaskette/marketing-studio/issues/148), [I01 / #157](https://github.com/dbbaskette/marketing-studio/issues/157), [I04 / #154](https://github.com/dbbaskette/marketing-studio/issues/154), [I05 / #160](https://github.com/dbbaskette/marketing-studio/issues/160), [R03 / #161](https://github.com/dbbaskette/marketing-studio/issues/161), [R04 / #162](https://github.com/dbbaskette/marketing-studio/issues/162)

**Delivery:** First release

**Paths:** `studios/infographic/runner/engine.py`, `studios/infographic/runner/desk_store.py`, `core/studio_core/drafting/`, `studios/infographic/tests/test_engine.py`

Work:

- Implement capture, extract, propose, story checkpoint, specify image, generate/compose, inspect/check/repair, page checkpoint, and export.
- Reuse shared drafting store/settle rules and keep studio-specific orchestration local.
- Support automatic draft by recording the recommended story choice while still requiring final approval.
- Persist atomic transitions, owned jobs, expected revisions, dependency snapshots, and approval invalidation; do not import legacy review-level machinery.

Acceptance criteria:

- [ ] All three direction modes share one saved workflow and are resumable after interruption.
- [ ] Only the user approves; stage workers cannot grant approval or publish.
- [ ] A job lands only on its unchanged input basis; stale mutations and outputs are refused.
- [ ] No new-work path depends on retired guided creation, a browser being open, or a nested planning assistant.

**Verification:** Scripted end-to-end engine tests for every mode, checkpoint, source change, automatic draft, stop/restart, concurrent changes, and failed export.

#### W02: build source intake and story selection on the shared editing desk

**Issue:** [#164](https://github.com/dbbaskette/marketing-studio/issues/164) · **Epic:** [#141](https://github.com/dbbaskette/marketing-studio/issues/141)

**Prerequisites:** [W01 / #163](https://github.com/dbbaskette/marketing-studio/issues/163), [S03 / #156](https://github.com/dbbaskette/marketing-studio/issues/156)

**Delivery:** First release

**Paths:** `studios/infographic/runner/web/index.html`, `studios/infographic/runner/web/app.js`, `studios/infographic/runner/web/infographic.css`, `ui-kit/style.css`, `ui-kit/drafting.js`

Work:

- Create the home/list and a three-step new-infographic sheet for information, direction, and page preferences.
- Show CSV selection, unsupported input, story alternatives/thumbnails, must-show coverage, omissions, and unresolved source gaps.
- Use shared Golden Gate controls and opaque reading/form surfaces with keyboard operation and responsive layout.
- Expose image-brief inspection as an optional detail, not another mandatory approval screen or review-level chooser.

Acceptance criteria:

- [ ] A user can start directed, suggested, or hybrid work and choose/edit a story from the desk.
- [ ] Optional fields remain progressive; required inputs and assumed defaults are visible.
- [ ] Actions remain usable at narrow widths, with 44 px touch targets and no clipping.
- [ ] Provider prerequisites are shown honestly and opening the sheet starts no provider work.

**Verification:** DOM interaction tests and fake loopback journeys covering all modes, sparse/overfull sources, keyboard focus, and narrow-screen source-sheet return behavior.

#### W03: build full-page review, focused edits, and approval/export controls

**Issue:** [#166](https://github.com/dbbaskette/marketing-studio/issues/166) · **Epic:** [#141](https://github.com/dbbaskette/marketing-studio/issues/141)

**Prerequisites:** [W02 / #164](https://github.com/dbbaskette/marketing-studio/issues/164), [W04 / #165](https://github.com/dbbaskette/marketing-studio/issues/165), [R04 / #162](https://github.com/dbbaskette/marketing-studio/issues/162), [I05 / #160](https://github.com/dbbaskette/marketing-studio/issues/160)

**Delivery:** First release

**Paths:** `studios/infographic/runner/web/review.js`, `studios/infographic/runner/api.py`, `studios/infographic/tests/test_review_api.py`

Work:

- Show the complete page with actual-size zoom, story/source/check details, image brief, and generation progress.
- Implement direct text edits, named-block requests, layout alternatives, undo/history access, and exact-revision approve/export.
- Preserve unaffected wording, data, artwork, and requirements during scoped changes.
- Show missing inspection/manual verification and unresolved blockers without claiming the page passed.

Acceptance criteria:

- [ ] A focused edit affects only the intended scope and invalidates only dependent checks/approval.
- [ ] Final approval is refused for outdated revisions or blocking findings.
- [ ] An in-progress or failed revision never replaces the last complete page or approved delivery.
- [ ] Draft downloads, approved exports, and acknowledged editorial advice have distinct visible states.

**Verification:** Interaction/API journeys for targeted text/data/art/layout changes, manual review, blocked approval, late results, preview reconnect, and export retry.

#### W04: add immutable history, compare, restore, and dependency-aware invalidation

**Issue:** [#165](https://github.com/dbbaskette/marketing-studio/issues/165) · **Epic:** [#141](https://github.com/dbbaskette/marketing-studio/issues/141)

**Prerequisites:** [W01 / #163](https://github.com/dbbaskette/marketing-studio/issues/163)

**Delivery:** First release

**Paths:** `studios/infographic/runner/history.py`, `studios/infographic/runner/desk_store.py`, `core/studio_core/drafting/versions.py`, `studios/infographic/tests/test_history.py`

Work:

- Adapt shared version history to story blocks, scene elements, briefs, source snapshots, and generated assets.
- Implement compare and restore as new revisions, never destructive rewrites.
- Track dependency changes so source, brand, text, data, and geometry edits invalidate the right derived work.
- Preserve original images, prior briefs, last complete preview, and approved exports through cancellation and recovery.

Acceptance criteria:

- [ ] Restoring an earlier revision does not restore approval automatically.
- [ ] Unchanged elements and assets are reused when their dependency basis still matches.
- [ ] Interrupted writes and corrupt/incomplete attempts do not erase valid history.
- [ ] History content remains in the private workspace and is not inserted into public issue/log records.

**Verification:** Disposable version-store tests for restore, parallel edits, changed source/brand hashes, partial saves, cancellation, and previous-export retention.

### E6: Marketing Studio integration and distribution

**Epic:** [#142](https://github.com/dbbaskette/marketing-studio/issues/142) · **Roadmap:** [#136](https://github.com/dbbaskette/marketing-studio/issues/136)

Add shared setup, launch, conversation entry, and independent suite/subset distribution without moving workspaces or weakening other studios.

**Exit gate:** Infographic Studio launches independently and through Marketing Studio, consumes the existing settings authority, supports conversation starts without nested planning assistants, and installs from source-independent bundles.

#### D01: integrate shared settings and provider capability reporting

**Issue:** [#155](https://github.com/dbbaskette/marketing-studio/issues/155) · **Epic:** [#142](https://github.com/dbbaskette/marketing-studio/issues/142)

**Prerequisites:** [F04 / #148](https://github.com/dbbaskette/marketing-studio/issues/148), [I02 / #151](https://github.com/dbbaskette/marketing-studio/issues/151), [I03 / #152](https://github.com/dbbaskette/marketing-studio/issues/152), [S04 / #150](https://github.com/dbbaskette/marketing-studio/issues/150)

**Delivery:** First release

**Paths:** `studios/infographic/runner/settings.py`, `studios/infographic/runner/computer.py`, `core/studio_core/preferences.py`, `core/studio_core/studios_config.py`, `core/studio_core/setup_web/`

Work:

- Read compatible shared assistant/model/reasoning/identity/workspace/brand settings from the existing settings authority and snapshot them for new jobs.
- Use the adjacent settings lock and lossless leaf updates, preserving unrelated values and refusing conflicting outdated forms.
- Keep page/image defaults studio-specific; never reinterpret deck delivery preferences as infographic outputs.
- Report Codex image access or Claude Code plus Gemini prerequisites and document environment inheritance for terminal and desktop launch without displaying or persisting the key.

Acceptance criteria:

- [ ] Changing shared defaults cannot move a configured workspace or mutate active-run selections.
- [ ] Codex does not ask for a Gemini key; Claude Code alone cannot start a production build.
- [ ] The UI distinguishes configured, locally detectable, not-yet-live-verified, and unavailable capabilities.
- [ ] Setup/preview/status never creates a test image or silently installs/updates tools.

**Verification:** Disposable shared-settings concurrent/stale form tests, inherited-default cases, launch-environment fixtures, and secret-sentinel API responses.

#### D02: add Marketing Studio discovery, launch, lifecycle, and CLI support

**Issue:** [#167](https://github.com/dbbaskette/marketing-studio/issues/167) · **Epic:** [#142](https://github.com/dbbaskette/marketing-studio/issues/142)

**Prerequisites:** [D01 / #155](https://github.com/dbbaskette/marketing-studio/issues/155), [W03 / #166](https://github.com/dbbaskette/marketing-studio/issues/166)

**Delivery:** First release

**Paths:** `marketing_studio/catalog.py`, `marketing_studio/cli.py`, `marketing_studio/launcher.py`, `marketing_studio/web/`, `core/studio_core/runtime.py`, `tests/test_launcher.py`, `tests/test_cli.py`

Work:

- Register the full product name, studio identifier, native entry, workspace convention, version, and status/doctor reporting.
- Add a discoverable launch card and native-to-Marketing Studio return link using the existing private handoff protocol.
- Support repeated launch reuse, owned shutdown, logs/redaction, failure messages, and optional LAN bridge behavior when enabled.
- Audit all three-studio enumerations instead of assuming a catalog entry covers setup, runtime, packaging, and tests.

Acceptance criteria:

- [ ] Marketing Studio opens the same configured Infographic Studio that the native command opens.
- [ ] Independent launch needs no running Marketing Studio, and missing installation does not trigger installation.
- [ ] Closing Marketing Studio stops only children it owns; live-provider work is not started during launch checks.
- [ ] Existing three studios retain their launch/lifecycle behavior and private session keys never enter durable logs.

**Verification:** Root catalog/CLI/launcher tests plus disposable native launch/reuse/shutdown and LAN-origin/session fixtures.

#### D03: add the native conversation skill and checked desk commands

**Issue:** [#168](https://github.com/dbbaskette/marketing-studio/issues/168) · **Epic:** [#142](https://github.com/dbbaskette/marketing-studio/issues/142)

**Prerequisites:** [W01 / #163](https://github.com/dbbaskette/marketing-studio/issues/163), [W03 / #166](https://github.com/dbbaskette/marketing-studio/issues/166), [D01 / #155](https://github.com/dbbaskette/marketing-studio/issues/155)

**Delivery:** First release

**Paths:** `studios/infographic/skills/infographic-studio/SKILL.md`, `studios/infographic/bootstrap/infographic-studio/SKILL.md`, `studios/infographic/guidance/manifest.json`, `studios/infographic/runner/studio.py`

Work:

- Provide native conversational create, inspect, direct, suggest, revise, approve, and export entry points backed by the same saved contracts.
- Let the current Claude Code or Codex session author story/image briefs directly rather than scheduling a nested planning assistant.
- Route Claude Code image requests through the server-side Gemini adapter and Codex image work through the scoped built-in route.
- Respect workspace ownership, expected revisions, exact wording, source permissions, and runtime/guidance compatibility.

Acceptance criteria:

- [ ] A conversation can start and revise desk work without opening a browser.
- [ ] Focused requests remain scoped and never reset the whole story or silently approve/export.
- [ ] No secret is inserted into assistant prompts or command arguments.
- [ ] Minimum-runtime guidance and native command help agree and do not restore retired gated creation.

**Verification:** Scripted native command/skill contract tests covering both assistants, browser-free creation, focused edits, stale mutations, and minimum-runtime refusal.

#### D04: package independent and suite installers with pinned rendering support

**Issue:** [#169](https://github.com/dbbaskette/marketing-studio/issues/169) · **Epic:** [#142](https://github.com/dbbaskette/marketing-studio/issues/142)

**Prerequisites:** [D02 / #167](https://github.com/dbbaskette/marketing-studio/issues/167), [D03 / #168](https://github.com/dbbaskette/marketing-studio/issues/168), [F02 / #146](https://github.com/dbbaskette/marketing-studio/issues/146)

**Delivery:** First release

**Paths:** `studios/infographic/installer/`, `studios/infographic/install.sh`, `core/studio_core/bundles.py`, `core/studio_core/offline_install.py`, `installer/install.py`, `scripts/build_bundles.py`, `pins/`

Work:

- Add native skill/launcher/install metadata, suite/subset selection, archive inventory, executable permissions, and required pinned render companions.
- Audit studio enumerations in build/bootstrap/distribution/acceptance paths and materialize approved shared links as ordinary installed files.
- Preserve explicit install/update actions, active-work refusal, rollback, and existing workspaces/settings.
- Keep API keys, generated content, prompts, source material, development paths, and private logs out of archives.

Acceptance criteria:

- [ ] An Infographic Studio-only bundle runs after the source checkout and extracted download are removed.
- [ ] Suite install/subset selection can include the fourth studio without changing existing selections.
- [ ] Deterministic archives verify hashes and missing/corrupt dependencies; no unpinned runtime download occurs.
- [ ] Rollback/uninstall retains content and settings, and independent native launch survives Marketing Studio removal.

**Verification:** Disposable build/install/rollback and source-independent subset/full archive acceptance with stub companions; run native platform bundle tests without providers.

### E7: verification and first-release readiness

**Epic:** [#143](https://github.com/dbbaskette/marketing-studio/issues/143) · **Roadmap:** [#136](https://github.com/dbbaskette/marketing-studio/issues/136)

Complete offline acceptance, visual and accessibility journeys, documentation, and release evidence for both supported configurations.

**Exit gate:** The full relevant Tart and native bundle checks pass on final source, documented provider acceptance is complete, and release limitations are explicit. Publishing remains a separate action.

#### Q01: wire offline regression and security acceptance into the shared runner

**Issue:** [#170](https://github.com/dbbaskette/marketing-studio/issues/170) · **Epic:** [#143](https://github.com/dbbaskette/marketing-studio/issues/143)

**Prerequisites:** [W03 / #166](https://github.com/dbbaskette/marketing-studio/issues/166), [D04 / #169](https://github.com/dbbaskette/marketing-studio/issues/169)

**Delivery:** First release

**Paths:** `studios/infographic/tests/`, `scripts/ci/check.sh`, `scripts/ci/native_acceptance.py`, `scripts/ci/native_launch_acceptance.py`, `scripts/ci/shared_setup_acceptance.py`, `scripts/ci/bundle_acceptance.py`

Work:

- Run the native suite and validator from the root gate and extend native setup/launch/bundle matrices to four studios.
- Add end-to-end synthetic workflows for all direction modes, both provider routes, numerical and conceptual pages, revisions, and exports.
- Exercise secret boundaries, source permissions, hostile assets/paths, expected revisions, limits, cancellation, crash recovery, and dependency invalidation.
- Keep unit/targeted checks with each implementation issue; this issue integrates coverage rather than deferring testing.

Acceptance criteria:

- [ ] No verification step touches personal settings/workspaces, real Git identity, signed-in providers, or real team content.
- [ ] Provider requests, key lookup, updates, installs, and network are denied or stubbed in automated fixtures.
- [ ] Existing Marketing Studio, Blog Studio, Presentation Studio, and Training Studio suites continue passing.
- [ ] Native independent setup/launch and suite/subset archives include the fourth studio without relying on the source tree.

**Verification:** Full relevant standard-library/native checks through the shared Tart entry point; inspect --dry-run before starting the owned disposable VM.

#### Q02: verify desktop, phone, accessibility, and actual-size visual journeys

**Issue:** [#171](https://github.com/dbbaskette/marketing-studio/issues/171) · **Epic:** [#143](https://github.com/dbbaskette/marketing-studio/issues/143)

**Prerequisites:** [Q01 / #170](https://github.com/dbbaskette/marketing-studio/issues/170), [W03 / #166](https://github.com/dbbaskette/marketing-studio/issues/166), [D02 / #167](https://github.com/dbbaskette/marketing-studio/issues/167)

**Delivery:** First release

**Paths:** `studios/infographic/tests/ui/`, `scripts/ci/`, `docs/design/golden-gate.md`, `studios/infographic/docs/acceptance.md`

Work:

- Exercise real loopback pages with fake providers and synthetic content at desktop and phone widths.
- Inspect intake, story choice, full-page zoom, image-brief detail, targeted edit, blockers, history, and download flows.
- Check dark/light, reduced transparency/motion, keyboard focus, semantic labels, contrast, readable text, and 44 px targets.
- Inspect actual rendered comparison, process, and conceptual exports at intended viewing size, not only scene coordinates.

Acceptance criteria:

- [ ] No horizontal overflow, clipped required controls, broken sheet returns, or material reading surfaces.
- [ ] Critical actions and findings are usable without hover or color alone.
- [ ] Every preset remains one page with legible labels and correct chart semantics.
- [ ] Visual verification evidence distinguishes stubbed workflow acceptance from live provider quality.

**Verification:** Repository-supported browser journeys and rendered-output inspection with disposable data; no personal browser session or provider jobs.

#### Q03: document setup and complete first-release sign-off

**Issue:** [#172](https://github.com/dbbaskette/marketing-studio/issues/172) · **Epic:** [#143](https://github.com/dbbaskette/marketing-studio/issues/143)

**Prerequisites:** [Q01 / #170](https://github.com/dbbaskette/marketing-studio/issues/170), [Q02 / #171](https://github.com/dbbaskette/marketing-studio/issues/171), [D04 / #169](https://github.com/dbbaskette/marketing-studio/issues/169)

**Delivery:** First release

**Paths:** `studios/infographic/README.md`, `docs/architecture.md`, `docs/installation.md`, `docs/packaging.md`, `docs/testing.md`, `docs/release-notes.md`, `studios/infographic/VERSION`

Work:

- Document both required setups, Gemini environment configuration for terminal/desktop launch, separate usage, supplied-only processing, local exports, typography/font limits, and recovery.
- Record supported runtime/renderer/platform combinations and explicit manual acceptance of generation, edit, and inspection for both provider routes.
- Run the full relevant suite once on final integrated source through Tart, then native source-independent bundle acceptance; rerun only affected checks after fixes.
- Prepare version/minimum-runtime/release notes and a release-readiness checklist; publication and real-user upgrades require a separate instruction.

Acceptance criteria:

- [ ] All first-release epic exit criteria and acceptance matrices are satisfied with accessible evidence.
- [ ] Automated suite success is not misreported as live provider validation or untested-platform support.
- [ ] Manual provider acceptance remains unfulfilled until explicitly requested and actually executed; no key is solicited into an issue.
- [ ] Known limitations are documented, and exported assets/content remain outside the application repository.

**Verification:** Review docs and install help against tested commands; retain sanitized conclusions while keeping machine-specific operational logs outside public repository content.

### E8: follow-up sources, research, and handoffs

**Epic:** [#144](https://github.com/dbbaskette/marketing-studio/issues/144) · **Roadmap:** [#136](https://github.com/dbbaskette/marketing-studio/issues/136)

Track richer intake, permissioned research, and cross-studio collaboration separately from the first release.

**Exit gate:** Each selected extension preserves source permissions, revision fidelity, private content boundaries, and the independently runnable studio architecture. These issues do not gate the first release.

#### L01: add PDF and Word source intake after the first release

**Issue:** [#173](https://github.com/dbbaskette/marketing-studio/issues/173) · **Epic:** [#144](https://github.com/dbbaskette/marketing-studio/issues/144)

**Prerequisites:** [Q03 / #172](https://github.com/dbbaskette/marketing-studio/issues/172)

**Delivery:** After first release

**Paths:** `studios/infographic/runner/sources.py`, `studios/infographic/runner/documents.py`, `studios/infographic/tests/test_document_sources.py`

Work:

- Add local PDF and Word extraction through compatible installed/pinned document readers.
- Capture original bytes, extracted text, page/paragraph locations, extraction limits, and source hashes.
- Handle scanned or unsupported content honestly and invalidate dependent facts on source updates.

Acceptance criteria:

- [ ] Unreadable pages and unsupported elements are visible coverage gaps.
- [ ] Original-to-text provenance remains available for checking claims.
- [ ] No implicit OCR/provider upload, arbitrary network fetch, or runtime dependency install occurs.

**Verification:** Disposable synthetic documents and stub extraction failures; native extraction acceptance only with explicit installed dependencies.

#### L02: add permissioned Google Docs and URL source intake

**Issue:** [#174](https://github.com/dbbaskette/marketing-studio/issues/174) · **Epic:** [#144](https://github.com/dbbaskette/marketing-studio/issues/144)

**Prerequisites:** [Q03 / #172](https://github.com/dbbaskette/marketing-studio/issues/172)

**Delivery:** After first release

**Paths:** `studios/infographic/runner/sources.py`, `studios/infographic/runner/remote_sources.py`, `studios/infographic/tests/test_remote_sources.py`

Work:

- Add explicit Google Docs selection and public URL capture using compatible account/source adapters.
- Pin retrieved revisions and preserve permission/capture failures without granting publication rights.
- Use shared validated public-address fetching and redirect checks for URLs; do not treat pasted links as fetch authorization.

Acceptance criteria:

- [ ] Each remote read requires the selected source action and records its captured revision.
- [ ] Private/loopback/link-local destinations, redirect bypasses, and credential-bearing URLs are refused.
- [ ] Account tokens and private source contents never enter shared settings or public tracking records.

**Verification:** Fake account/read transports and DNS/redirect fixtures; no signed-in account or live fetch in automated checks.

#### L03: integrate optional purpose-led shared research

**Issue:** [#175](https://github.com/dbbaskette/marketing-studio/issues/175) · **Epic:** [#144](https://github.com/dbbaskette/marketing-studio/issues/144)

**Prerequisites:** [Q03 / #172](https://github.com/dbbaskette/marketing-studio/issues/172)

**Delivery:** After first release

**Paths:** `studios/infographic/runner/research.py`, `core/studio_core/research_contract.py`, `studios/infographic/tests/test_research.py`

Work:

- Consume the existing schema-2 synthesis contract with infographic purpose, audience, scope, and explicit source mode.
- Retain independently reviewed evidence, conditions, counterfacts, gaps, captured sources, and digest checks.
- Keep supplied-only behavior separate from explicit public research and record exact run/helper revisions.

Acceptance criteria:

- [ ] Only verified complete bundles can feed new factual claims.
- [ ] Public research never occurs in supplied-only mode or through image-provider search/grounding.
- [ ] Stale or missing captures block claims/approval without replacing previously approved work.

**Verification:** Existing synthetic synthesis fixtures adapted for infographic stories, permission refusal, stale digest, and missing source capture cases.

#### L04: add explicit cross-studio and team workspace handoffs

**Issue:** [#176](https://github.com/dbbaskette/marketing-studio/issues/176) · **Epic:** [#144](https://github.com/dbbaskette/marketing-studio/issues/144)

**Prerequisites:** [Q03 / #172](https://github.com/dbbaskette/marketing-studio/issues/172)

**Delivery:** After first release

**Paths:** `studios/infographic/runner/handoffs.py`, `studios/infographic/runner/team.py`, `studios/infographic/tests/test_handoffs.py`, `docs/architecture.md`

Work:

- Import selected Blog Studio, Presentation Studio, or Training Studio material as a pinned source with an explicit user action.
- Add team ownership/takeover/share semantics consistent with current studio conventions and validated selected-file inventories.
- Preserve source permissions, missing local assets, prompt/art privacy, and independent run/revision approval.

Acceptance criteria:

- [ ] An import never means every local file is shared or that the new infographic is approved.
- [ ] Teammates see honest missing-asset and ownership states and can explicitly take over supported work.
- [ ] Changed originating content creates a new source revision rather than silently mutating an approved infographic.

**Verification:** Synthetic multi-workspace/local Git handoffs, missing assets, ownership conflict, source-change, and explicit-sharing tests.
