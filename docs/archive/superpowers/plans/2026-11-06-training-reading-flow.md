# Training Studio reading flow

Issue #415; authorized audit implementation and merge.

A healthy draft or Ready material gets a compact header with its title, explicit
state and existing actions. The reading surface owns the opaque paper. Successful
checks move into a stable, keyboard-accessible disclosure with the full status
explanation; review problems, outdated material, recovery and blocking states stay
visible. Mark ready remains an explicit creator action against the saved revision.

Documents with more than three sections use one labeled native section picker,
with the current section count and Edit/Done editing alongside it. Short documents
retain their tabs. Selection preserves focus, scroll, selected section and local
text. Editing no longer intentionally scrolls the page back to the top.

| Transition | Required result | Verification |
| --- | --- | --- |
| Healthy draft/Ready | Compact state/actions, optional successful-check details | Native reading browser |
| Problems or outdated material | Explanation and recovery remain visible | Existing desk review regressions |
| Select a long document section | One section shown, selector focus retained | Native browser |
| Switch away and back with local edits | Text retained | Native browser and desk regressions |
| Poll while reading/check details open | Selection and disclosure retained | Native browser |
| Mark ready | Same explicit version-bound decision | Existing desk readiness/save tests |

Before: in an eight-section synthetic guide, the reading paper begins 793px from
the page top at 1280px width and 641px at 390px. The fixture uses the real native
page with scripted authors and long section titles; these are layout positions,
not provider wall times.

After: 548px at 1280px and 530px at 390px, respectively 245px and 111px earlier.
Both measurements apply the matching responsive toolbar layout. The native
browser checks section focus, selection across refreshes, local text retention,
successful-check disclosure state and overflow in light and dark mode. The
existing reading journey covers short sections, Yoodli fields, Finishing and
sheet focus. No provider work is started.

The shared UI/layout checks passed all 47 tests. The rendered-slide journey passed
at 390/1280px in light/dark with scrolled selection, focus, caret and local edits
retained. Its scroll setup now deliberately scrolls the shorter page.

The full Training Studio suite ran 3,227 tests in 557 seconds in a disposable Tart
VM (macOS 27.0, Python 3.13.15, Node 22.23.2), on `43ab2512` plus this working tree.
It identified two adapter failures from registering a browser listener in a
non-browser context, and one stale briefing assertion that also fails on unchanged
`43ab2512`: the assertion omitted the already-shipped US English guidance. After
fixing registration and updating that expectation, all 102 affected desk tests,
all five briefing tests, the package validator and the native long-document browser
passed on the host. The remaining 3,120 suite tests passed unchanged in Tart; the
VM was deleted. This reuses the full run's unaffected evidence rather than
claiming a second complete run.
