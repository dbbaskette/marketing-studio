# Infographic Studio first-release acceptance

Implementation scope is Marketing Studio milestone 2. Offline verification does not
establish signed-in provider access, image fidelity or owner acceptance. Publication
and real-user upgrades require a separate instruction. Issues close only after merge
and their acceptance criteria are fulfilled.

## Reproducible checks

| Area | Evidence/check | Boundary |
| --- | --- | --- |
| Source capture and stories | `tests/test_sources_and_stories.py` | Exact raw/normalized hashes, CSV scope/types/units, located claims, literal measurement context, calculations, direction modes and required content; no provider |
| Composition | `tests/test_composition.py` | All six forms and three presets; with explicit test renderer, 18 actual PNG/PDF/SVG compositions; readable floors and no silent shrinking |
| Rendering | `tests/test_render.py` | Actual fonts, image decode, text bounds, overflow, PNG dimensions and exactly one PDF page; placeholder samples are not illustration-quality acceptance |
| Provider adapters | `tests/test_image_adapters.py`, `test_workers.py` | Injected CLI/HTTP only; no key leakage/fallback, actual owned bytes, minimal tools, bounded process groups, blocked-stdin timeout |
| Jobs and recovery | `tests/test_image_jobs.py` | Durable intent, duplicate IDs, cancellation, restart, changed-basis rejection, uncertain requests surviving content invalidation |
| Desk/approval/history | `tests/test_desk_engine.py` | Source-to-export workflow, scoped story/text/art edits, actual-pixel review contract, shared repair budget, exact user approval, immutable retryable delivery and restore |
| Native HTTP/CLI/install | `tests/test_server.py`, `test_cli.py`, `test_installer.py` | Real loopback auth/Host/Origin limits, idempotent creation, CSV validation before creation, source-independent commands, rollback, active-work refusal and preservation |
| Browser | `tests/ui/journey.cjs` | Real native page and renderer, injected assistant; intake to approved download, focused edit, actual-pixel zoom, comparison, 320/390/1280 widths, light/dark, reduced motion/transparency, keyboard dialog return and 44 px controls |
| Marketing Studio integration | Root `tests/test_infographic_release.py` and existing suites | Catalog, CLI flags, lifecycle, shared setup, fixed LAN bridge, deterministic subset inventory and minimal dependencies |
| Clean platform install | `scripts/ci/infographic_bundle_acceptance.py` | Prepared private runtime and renderer, real native export, extracted download removed, Marketing Studio removed, no system Python/Node or provider/provisioning calls |

From the repository root, the shared full check is `scripts/ci/check.sh PYTHON RESULTS`.
The dedicated Tart entry point is:

```sh
bash scripts/ci/tart-macos.sh --guest scripts/ci/guest-infographic.sh --dry-run
bash scripts/ci/tart-macos.sh --guest scripts/ci/guest-infographic.sh
```

That guest uses the existing disposable runner and full relevant suite, explicitly
prepares checksum-pinned rendering and locked browser-test tooling inside its clone,
then runs the browser and source-independent package journeys. Tests themselves do
not provision software or start providers. Supply a prepared Infographic Studio-only
Apple Silicon archive under `dist/infographic-first-release-*-macos-arm64.zip`.
Retain detailed operational logs outside the public repository and identify the
actual source tree and guest environment in those logs.

## Platform matrix

| Platform | Renderer pin | First-release acceptance |
| --- | --- | --- |
| macOS ARM64 | Chrome headless shell 145.0.7632.6, archive and executable hashes pinned | Target platform for real render, browser, Tart and prepared native package acceptance |
| macOS x64 | Same renderer version, hashes pinned | Foundation renderer feasibility passed; new native package requires separate platform acceptance before publication |
| Linux x64 | Same renderer version, hashes pinned | Archive checksum verified; runtime, fonts and native package acceptance remain unverified |
| Linux ARM64 / Windows | No supported renderer pin | Refused before preparing an Infographic Studio platform bundle; existing studio subsets retain their own support |

Application runtime is Python 3.11+. Prepared runtime versions are fixed in
`pins/runtimes.json`, rendering in `pins/infographic-renderer.json`, browser-test-only
tooling in `tests/ui/package-lock.json`. Exact fonts and the selected brand's own
local prerequisites remain explicit. Fonts are not silently substituted or shipped.

## Separate live and owner gates — pending

Do not mark these passed from mocks, command help, a saved prompt or a success message.
Before a live request, obtain the user's explicit request for this acceptance action
and disclose the selected model/provider and separate Gemini usage. Never solicit a
key into an issue or store it in a project. Use synthetic content in a separate local
workspace, not private team material.

1. **Codex route:** actually generate a saved PNG through the signed-in built-in image
   tool, make a reference-guided edit, inspect the actual original and composed PNG,
   verify usage/unknown status, then exercise failure/recovery without replaying it.
2. **Claude Code + Gemini route:** actually generate and reference-edit a PNG through
   the explicit image-capable model, inspect actual images through the confined
   Claude Code Read path, and verify normalized model/key/quota/uncertain outcomes.
   A local-key presence check is not model-access verification.
3. **Owner illustration review:** show an illustration-led conceptual page, an
   illustrated process and a mixed chart-and-illustration page, with actual artwork
   and composed exports. Review explanatory value, counts/relationships, coherent
   style, crop/aspect, output resolution, label clearance, brand and factual implications.
   Basic bars, connector boxes, solid PNG markers and fixture screenshots do not count.
4. Confirm final approval and all four downloads for an accepted current revision;
   verify that a later source/brand/text/art change invalidates approval. Keep owner
   decisions and generated material in the separate workspace, not this repository.
5. Record sanitized acceptance conclusions, required platform evidence and remaining
   limitations; obtain a separate publication/upgrade instruction.
