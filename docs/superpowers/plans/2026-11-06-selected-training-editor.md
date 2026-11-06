# Training Studio selected editor loading

Issue #412. The approved audit includes implementation, verification and PR merge.

## Contract

Keep the complete material metadata and navigation, but load only the selected
editor on entry and refresh. Load other editors when selected; retain their local
state and reuse an unchanged loaded revision. Finishing discovers all eligible
materials from metadata, including unvisited ones. A failed read has an explicit
retry. No provider, approval, save or ownership behavior changes.

## Implementation

1. Resolve selection before loading; deduplicate concurrent requests per material.
2. Protect pending, saving and conflicted text; reject responses for superseded
   metadata. Keep focus and page ownership when asynchronous reads complete.
3. Show loading/retry feedback and record a material as opened only after its
   current content is available. Deck previews continue using their metadata.
4. Exercise native desk regressions and a real browser journey; compare the same
   five-material fixture before and after. Run the relevant complete suite locally.

## State-transition matrix

| Event | Result | Verification |
| --- | --- | --- |
| Entry or full refresh | Only selected editor requested | Native browser request counts |
| Select unvisited material | Loading, then reading surface or retry | Browser and desk regression |
| Failed or background editor load | Current revision not marked opened | Native browser |
| Response after selecting another material | Selection and local edits retained | Native browser |
| Pending save or recovered conflict | Local revision remains authoritative | Existing desk recovery regressions |
| Finishing chooses unvisited material | Load that editor, then open its tools | Desk regression |
| Return to a loaded unchanged material | Reuse editor and editing state | Browser and desk regression |

## Measurement

Baseline on the unchanged `9811c077` tree: five editor requests per full refresh,
89,495 response bytes; five loopback samples 242, 242, 245, 256, 258 ms (median
245 ms). The fixture contains five completed materials, uses scripted authors,
and excludes a fixed 30 ms browser response-settling delay. These are synthetic
local read measurements, not provider generation timings.

After: one editor request, 15,904 response bytes; samples 110, 110, 113, 114,
114 ms (median 113 ms). This removes 80% of editor requests, 82% of editor bytes,
and 54% of measured full-refresh wall time in this fixture. No claim is made
about authoring/model latency.

The native browser covers initial/refresh request counts, lazy selection, failed
load and retry, late completion after changing material, retained unsaved text,
cached return, accurate opened revisions and no new jobs. The rendered-slide
journey also passed at 390/1280px in light/dark, preserving scroll, focus, caret,
selection and local slide text. The shared layout/UI checks passed (47 tests).
The disposable Tart run passed the affected complete desk, settings and layout
modules (484 tests) and package validation on macOS 27.0, Python 3.13.15 and
Node 22.23.2. A final saved-version bookkeeping adjustment passed all 100 desk
screen journeys on the host; it changes no shared runtime or save contract.
