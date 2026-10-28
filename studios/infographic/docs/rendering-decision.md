# Infographic Studio rendering decision

## Selection and boundary

Use an explicitly installed **Chromium headless shell** to measure a self-contained
SVG, produce PNG at the requested viewport dimensions, and print a single-page PDF
with CSS page dimensions and zero margins. Application orchestration remains
standard-library Python; there is no frontend build or browser download at runtime.

The command-surface and local rendering baseline for this spike is Chrome for
Testing 145.0.7632.6. This is an exact tested baseline, not a claim that it is the
latest browser or that other versions are compatible. The first-release packaging
issue must complete redistribution notices, supported-platform integrity locks,
and the retained runtime before enabling a production download. The feasibility
pin in `pins/infographic-renderer.json` locks the official macOS x64 archive and
executable hashes; its executable matches the one used for the smoke checks.
No companion or
runtime lock used by another studio is changed by this spike.

The browser is an external rendering dependency; having Python alone does not
provide font metrics, PNG rasterization, or PDF output. The native foundation does
not advertise exports as an implemented product workflow. `runner/render.py` and
the graphics command are a reusable, tested feasibility adapter for the later
scene and export issues.

## What is demonstrated

| Preset | PNG | PDF page dimensions |
| --- | --- | --- |
| A4 portrait | 2480 × 3508 px, 300 dpi rounded | 210 × 297 mm |
| US Letter portrait | 2550 × 3300 px, 300 dpi | 612 × 792 pt |
| Digital portrait | 1080 × 1350 px | 810 × 1012.5 pt (96 dpi CSS interpretation) |

Synthetic comparison, process, and conceptual pages exercise actual text, shapes,
connectors, and an embedded PNG marker. Tests inspect raster headers, the generated
PDF's page objects and dimensions, editable SVG text nodes, and the PDF font
Unicode mapping. The PDF inspector intentionally handles this renderer's own
ordinary PDF objects; it is not an arbitrary-document intake parser.

Font availability is checked with local FontFace loading, not a generic CSS
fallback test. The browser measures actual SVG text bounds. Missing fonts, labels
outside their reserved regions, and geometry outside the page block publishing
the attempt. Text wrapping is represented by explicit SVG text spans rather than
scaling labels down; layout authoring remains a later issue. Glyph fallback and
font redistribution rights require brand-specific acceptance; merely finding a
font does not prove it contains every requested glyph or may be embedded.

The original SVG preserves text and chart geometry. Generated raster artwork
remains raster when embedded in SVG/PDF; it is not magically editable as vectors.
Print documents are RGB, without press-ready bleed/CMYK or PDF accessibility tags.

## Isolation and failure handling

- An explicit executable path is required; never discover a personal browser
  profile or silently install one.
- Each render uses an owned disposable profile and HOME, with no provider keys,
  account state, extensions, background updating, or DNS resolution.
- Only validated SVG elements/attributes and embedded PNG/JPEG references are
  accepted. Scripts, external resources, links, entities, style attributes, and
  foreign content are refused before opening the document.
- Font/layout measurement must complete before exports run. Output files are
  published into a new destination folder only after PNG/PDF verification.
- A timeout terminates the renderer's owned process group. A failed attempt cannot
  replace earlier output. The production scheduler will supply revision ownership
  and total attempt accounting in later work.

## Supported evidence and packaging gate

Local real rendering has been exercised on macOS x64. macOS ARM64 and Linux x64
require native acceptance and integrity-locked platform archives before being
advertised. Chrome for Testing does not provide the same official Linux ARM64
distribution; treat Linux ARM64 rendering as unsupported until an alternative is
explicitly selected and tested. Windows is outside Marketing Studio's scope.

This evidence does not establish branded layout quality, image-provider quality,
or every font's portability. User visual confirmation of the surfaced synthetic
outputs is separate from automated geometry checks.

## Reproduce and inspect the actual graphics

From the repository root, with Python 3.11+:

```sh
python3 studios/infographic/scripts/graphics_smoke.py \
  --renderer /path/to/installed/chrome-headless-shell \
  --output /path/to/an/empty/folder/outside/the/application
INFOGRAPHIC_STUDIO_TEST_RENDERER=/path/to/installed/chrome-headless-shell \
  python3 -m unittest discover -s studios/infographic/tests -v
```

The command leaves comparison/A4, process/Letter, and concept/digital PNG, PDF,
SVG, and measurement files for visual inspection. Its default output is a new
temporary directory outside the repository. It makes no assistant or image calls.

Primary references: [Chrome headless operation](https://developer.chrome.com/docs/chromium/headless)
and [Chrome for Testing availability](https://googlechromelabs.github.io/chrome-for-testing/).
