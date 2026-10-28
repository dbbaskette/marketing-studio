# Infographic Studio

Turn supplied information into one clear page. Add notes, a UTF-8 text/Markdown
file or an explicitly selected CSV table; choose a story; build and inspect the
page; make focused edits; approve the exact revision and download PNG, one-page
PDF, editable SVG and accessible text. Explanatory artwork stays raster inside
SVG; labels and chart marks remain editable.

The first release implements comparison, process, timeline, number callouts,
parts-to-whole and conceptual explanations in A4, US Letter and 1080 × 1350 digital
portrait. It does not fetch URLs, conduct research, import Office/Google documents,
or share content into team repositories. Those follow-up integrations are tracked
separately. Sources and generated files stay in your local workspace.

## Start

Use Marketing Studio's Infographic Studio card, `marketing-studio open infographic`,
or `marketing-studio start --is --lan` for an explicitly enabled trusted phone/LAN
session. Native launch and setup also work independently:

```sh
python3 runner/studio.py status
python3 runner/studio.py serve --open
```

A missing shared configuration opens the same shared setup used by the other
studios. Finishing setup or launching explicitly creates a missing local workspace;
existing workspaces are preserved. Shared assistant, model, effort and brand choices
remain authoritative. Infographic Studio uses local storage even when other studios
use the shared team repository; no repository content is moved, cloned or pushed.
The native Settings screen opens shared setup and separate image/renderer defaults.

Python 3.11+, Git and a compatible headless Chromium renderer are required. Prepared
supported-platform packages include private Python, Node and a checksum-pinned
renderer. Node supports installed brand add-ons; the Infographic Studio pipeline
uses Python's standard library, no frontend build, no image SDK, no Research or
Slides runtime. A separately installed brand add-on may have its own prerequisites:
the current Tanzu Brand shared-contract exporter requires Harness Slides 0.14.1+.
Nothing installs or updates those prerequisites automatically. A supplied resolved
brand contract can be adopted directly with the native `brand` command.

## Provider choices and usage

- **Codex:** uses the shared Codex model/effort and existing Codex sign-in. The native
  image adapter enables only the built-in image generation path; other text workers
  retain their existing confinement. No separate OpenAI image API key or fallback is
  requested. Image availability and account access remain unverified until a live run.
- **Claude Code + Gemini:** Claude Code plans and inspects; Gemini generates and edits
  images through the documented Interactions API. Set an image-capable Gemini model in
  native Settings. Generation requests PNG at 2K with a portrait aspect ratio, without
  search/tools or stored interaction history. The selected model must support those
  options; no silent downgrade or provider fallback occurs.

Set `GEMINI_API_KEY` only in the environment of the server process you explicitly
launch. For a terminal launch, export it in that terminal before launching the app.
For a desktop launch, use a launch environment you control that supplies the key;
a desktop app does not inherit an arbitrary terminal's exports. Do not paste keys
into shared settings, source material, prompts or an issue. Image API usage is
separate from Claude Code usage; Codex uses its existing account allowance. Only
reported token/cost data is shown; unknown prices are not estimated.

Assistant work starts only after an explicit action. Building an illustrated page
can use planning and image allowances; review the disclosure before starting it.
Actual-page inspection uses the selected assistant's multimodal path, or you can
record your own review after viewing the current PNG at intended size. CLI help
and capability discovery are not proof of account access or successful generation.

## Editing and recovery

The desk exposes direct copy edits, a named-block or whole-story revision, a precise
saved image brief, reference-guided artwork edits, pixel inspection, findings,
comparison, history, restore and all four downloads. Earlier deliveries are labeled
when they no longer match current content. Required content, locked wording, located
facts, exact calculations, readable fit and actual fonts are checked. Unknown units,
periods or denominators block quantitative comparisons rather than being invented.
Print body/source floors are 12/9 pt; digital floors are 24/18 px. A selected brand
can raise them. Missing or unlicensed fonts require explicit user action; no font
binaries are redistributed. Other computers need compatible fonts to edit SVG.

Image intent is durable before a provider call. Reopening never replays pending or
uncertain requests. A repeated request ID cannot spend again. Cancel revokes local
adoption and stops owned CLI children; remote cancellation/charges may remain
unknown. Image requests and reported usage remain inspectable after later edits.
Layout and image repairs share a two-attempt automatic repair budget. Manual edits
and a smaller story remain available afterward. Export retry verifies existing
files and never regenerates an image. Restore creates a new revision and never
restores approval. Only explicit user approval authorizes final delivery.

See [conversation commands](docs/conversation.md), [saved contracts](docs/contracts.md),
[renderer selection](docs/rendering-decision.md), [provider capabilities](docs/provider-capabilities.md)
and [release acceptance](docs/acceptance.md).

## Verification

```sh
python3 -m unittest discover -s tests -v
```

Tests use synthetic material, disposable HOME/settings/workspaces and injected
providers. `INFOGRAPHIC_STUDIO_TEST_RENDERER=/absolute/installed/headless-shell`
enables real rendering checks; the tests never download or install it. The browser
journey is `tests/ui/journey.cjs` using a separately available Playwright test runtime.
Live provider generation/edit/inspection and owner illustration acceptance remain
separate release gates, never inferred from fixture success.
