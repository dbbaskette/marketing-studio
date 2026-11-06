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

## Visible secondary actions — #402

Shared secondary buttons used transparent fills and decoration-strength borders.
Use opaque neutral control fills and explicit boundary tokens in both themes,
including the liquid pilot. Keep primary, selected and disabled states separate.

Verification: all 47 shared UI/layout checks passed. Browser measurements passed
3:1 inner/outer control boundaries and 4.5:1 label contrast on reading cards, 44px
targets, focus and forced colors, at 390/1280 px in light/dark and standard/pilot.
The actual Marketing Studio settings save/reload journey also passed. The slide
position change passed 139 Training Studio desk/layout tests and its rendered
slide browser journey before merging as #401.
