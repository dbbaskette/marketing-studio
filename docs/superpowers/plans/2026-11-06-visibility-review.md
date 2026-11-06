# Marketing Studio visibility review

The review covers control visibility, reading order, page length and stable navigation
on desktop and phone. Use synthetic workspaces and workers; never change a live
training to reproduce a layout problem. Implement and merge each issue separately.

## Slide review position — #400

Selecting a rendered slide currently uses full-page navigation, scrolling to the
training title. Replace only the selected slide card. Keep the selector mounted,
retain per-slide unsaved text, and give the selector a stable focus key for polling.

| State / action | Expected result | Evidence |
| --- | --- | --- |
| Scrolled deck + select another slide | Same selector, focus and viewport position | rendered slide browser journey |
| Unsaved text + switch away/back | Text retained for that slide | same journey |
| Poll during editing | Selection, focus and caret retained | same journey |
| Selection / local typing | No provider job or saved-material write | fake-worker job count and existing save boundary |

Verify the affected Training Studio desk/layout modules and the rendered deck
journey at 390/1280 px, light/dark. Reuse broader unchanged runtime evidence.
