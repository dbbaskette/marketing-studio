# Provisional slide preview decision — issue #363

## Decision

Retain the sealed render-bundle boundary in production. The experiment proves a
substantial early-display opportunity for large decks, but does not establish the
complete dependency and publication contract needed to expose temporary renderer
output safely. Do not ship the prototype's staging-file interception as a shortcut.
No second renderer, provider calls, Google work or approval changes were introduced.

This is a completed feasibility spike, not a claim that streaming previews are
undesirable or that production already streams them. The next implementation would
need a helper-owned per-slide event contract and native adapters before adoption.
The small-deck edit gain alone does not justify that additional state machine.

## Measured display, not file appearance

Harness Slides 0.17.0, pinned commit
`fecfe2b63de0620e6c5cbad841d11cf37ecf3d61`, existing LibreOffice/Poppler renderer,
macOS ARM64, Node 26.11.1. One synthetic trial at each size; cold, unchanged and
one-slide edit run sequentially within a fresh cache. No user content or brand.
The edited slide is the middle slide, and the provisional image is that changed
slide, not a cached opening slide.

The isolated visible viewer polls every 50 ms, decodes the current attempt's PNG,
waits two animation frames, then acknowledges its display to the local server.
Times below include compilation and rendering from attempt start. They are single
observations, not medians or a production tail estimate. Final display means the
sealed bundle is available in the viewer, not owner approval.

| Slides | Case | First raster (s) | Provisional display (s) | Sealed bundle (s) | Final display (s) | Display gain (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 6 | Cold | 1.569 | 1.705 | 2.202 | 2.305 | 0.600 |
| 6 | Unchanged | — | — | 0.251 | 0.331 | — |
| 6 | One-slide edit | 1.471 | 1.659 | 1.720 | 1.795 | 0.135 |
| 30 | Cold | 1.546 | 1.636 | 4.694 | 4.770 | 3.134 |
| 30 | Unchanged | — | — | 0.261 | 0.361 | — |
| 30 | One-slide edit | 1.549 | 1.706 | 2.656 | 2.745 | 1.038 |
| 100 | Cold | 1.786 | 1.880 | 12.438 | 12.523 | 10.643 |
| 100 | Unchanged | — | — | 0.295 | 0.376 | — |
| 100 | One-slide edit | 1.794 | 1.965 | 5.426 | 5.505 | 3.540 |

Cold cases rasterized 6/30/100 slides, unchanged cases zero, and edits one. Existing
cache reuse therefore remains valuable. The visible screenshot showed the changed
middle slide after completion. First-raster timing alone would have overstated the
benefit by roughly 90–190 ms in these trials.

## Binding and failure investigation

The prototype waits for a successful raster process return, decodes the PNG, hashes
its bytes, copies them into an immutable response, and checks an attempt ID and a
compiled-input digest before publication. Image requests from superseded attempts
are refused. The viewer has no approve/export action and labels provisional output.
Its guard rejects cancellation, supersession, failed state, changed scope, changed
image bytes, a missing packet and a corrupt PNG.

Separate fault probes use the real renderer and interrupt after the first complete
raster. Partial failure, cancellation and supersession each clear the candidate,
produce no final output, and leave no partial staging bundle. These are cancellation
at a confirmed tool return; they do not prove in-flight process termination. The
existing helper's 13 preview and 11 workflow-integrity tests passed, including
missing renderer/page errors, corrupt immutable assets, corrupt/missing cached
bundles, one-slide reuse and exact critique binding.

The remaining production gap is material: the prototype's top-level compiled-input
digest does not include the helper's complete resolved font, runtime, brand-source,
external asset and per-slide dependency identities. The real helper computes those
privately before rendering and seals them with the final artifact. Exposing `.stage`
files from a native adapter would duplicate that authority and add another race
between cancellation, source invalidation, preview publication and final approval.
A production implementation should emit a typed, helper-owned provisional event
with those exact identities, bounded immutable bytes and explicit revocation, then
verify native cancellation/reconnect and final-bundle promotion. None of those gates
should be weakened merely because an image is decodable.

## Reproduce

Run `node scripts/performance/provisional-preview-spike.mjs HELPER NEW_SCRATCH`,
then open its printed loopback viewer. The viewer starts the experiment and records
its own display acknowledgements. `BENCH_COUNTS` can limit sizes. A missing browser
acknowledgement stays `null`; it is never substituted with file-creation time.
The server stays open for inspection; stop that owned process when finished.

Run `node scripts/performance/provisional-preview-faults.mjs HELPER COMPILED_DIR`
against a disposable compiled case from the experiment to check interruption cleanup.
Use the existing pinned helper and installed renderer dependencies. No live provider
or Google setup is needed. The scripts are experiments, not studio runtime entrypoints.
