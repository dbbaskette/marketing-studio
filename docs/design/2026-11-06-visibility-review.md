# Studio UI visibility review — November 6, 2026

This review covered reading order, control visibility, page length and stable
navigation across Marketing Studio, shared settings and the four native studios.
It followed the [Golden Gate design rules](golden-gate.md). Browser verification
used disposable workspaces and synthetic material, with no live provider jobs.

## Findings and resolutions

| Finding | Change | Tracking |
| --- | --- | --- |
| Selecting a rendered training slide scrolled to the page title. | Replace only the slide card; keep the selector, viewport position and per-slide unsaved text. Background polling retains focus and caret. | [#400](https://github.com/dbbaskette/marketing-studio/issues/400), merged [#401](https://github.com/dbbaskette/marketing-studio/pull/401) |
| Secondary buttons blended into reading surfaces. | Shared opaque control fills and visible boundaries in light/dark, including the liquid pilot. Primary and disabled states stay distinct. | [#402](https://github.com/dbbaskette/marketing-studio/issues/402), merged [#403](https://github.com/dbbaskette/marketing-studio/pull/403) |
| Many practice scenarios and deck controls made Training Studio review too long. | Group repeated Practice/Yoodli materials with item selectors; separate Preview, Text & notes, and Review & changes; disclose Deck actions below the slide. A 14-material fixture now has seven top-level choices instead of fifteen. | [#404](https://github.com/dbbaskette/marketing-studio/issues/404), merged [#405](https://github.com/dbbaskette/marketing-studio/pull/405) |
| Quick scan controls were cramped, explanations dominated the form, and settings were a long stack. | Pad and align Quick scan controls, shorten the main explanation, and disclose details. Show one shared-settings section at a time, with a compact phone selector. Training Studio Change settings uses Teaching, Materials and Research, with a separate action footer. | [#406](https://github.com/dbbaskette/marketing-studio/issues/406), merged [#407](https://github.com/dbbaskette/marketing-studio/pull/407) |
| A generated slide used British spelling. | Remove British spelling from authoring examples and add a shared US English default, while honoring explicit language requests and preserving quotations and approved wording. | [#408](https://github.com/dbbaskette/marketing-studio/issues/408), merged [#409](https://github.com/dbbaskette/marketing-studio/pull/409) |
| TrueSource was absent from the brand catalog. | Correct the shared runtime selection to Harness Brand and its data repository to broadcom-brands. Verify all four brands and a TrueSource slide contract; document both settings. | [#410](https://github.com/dbbaskette/marketing-studio/issues/410), [setup guide](../shared-setup.md#harness-brand-and-the-four-brands) |

## Cross-studio review

| Surface | Result |
| --- | --- |
| Marketing Studio and shared settings | Home and settings checked on desktop and phone; one selected settings section, reachable save controls and visible secondary actions. |
| Training Studio | Rendered-slide review, repeated materials, unsaved edits, settings validation and sheet focus/scroll checked. |
| Presentation Studio | Existing one-slide reading desk and folded summary remained suitable; shared control improvements apply. |
| Blog Studio | Existing reading view, compact phone toolbar and View and tools disclosure retained. Checked settled responsive layout, overflow and browser errors. |
| Infographic Studio | Existing task views retained. Broader browser journey covered desktop/phone, keyboard dialogs, reduced effects and enlarged text. |

## Verification and limits

Affected module suites passed at each implementation boundary: 139 Training Studio
desk/layout checks, 65 shared UI/layout/settings checks, 72 Training Studio
settings/layout checks, and 63 authoring/outline/deck handoff checks. Earlier
unchanged module evidence was reused where appropriate.

Browser journeys exercised 390/1280 px in light and dark, with the broader
Marketing Studio/Infographic Studio journey also covering 320/768/1440 px. Control
checks measured 3:1 boundary contrast against the fill and reading surface, 4.5:1
label contrast, 44px targets, focus and forced colors. Settings journeys covered
unsaved section changes, hidden invalid fields, save/reload, cancel and focus
return. These are UI and behavior checks, not a new provider-speed benchmark or
an assessment of generated artwork.

The configured Harness Brand catalog returned all four brands. A disposable
TrueSource light slide contract exported and validated against current local
sources. Existing training brand choices and generated text were preserved.
US English is guidance for future authoring, not a rewrite of existing slides or
a deterministic spell checker.

See the [implementation and verification plan](../superpowers/plans/2026-11-06-visibility-review.md),
[shared settings guide](../shared-setup.md) and
[Training Studio desk guide](../../studios/training/README.md#refine-the-training-on-the-desk).
