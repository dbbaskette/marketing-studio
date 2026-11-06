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

## Compact Training Studio review — #404

Group repeated Practice and Yoodli items, with a category count and an item selector
that names each item's state. Keep the existing individual tabs when there is one
item. Keep all material identities and approval/opened-version accounting intact.

Within a rendered slide, show Preview, Text & notes, or Review & changes. Keep
one selected task across slide choices and polling. Show the suggestion count on
the review tab; keep the material's overall blocked/ready state above the workspace.
Move whole-deck changes and alternate looks after the slide, under Deck actions.
All panes retain local edits; switching panes only changes visibility.

| State / action | Expected result | Regression |
| --- | --- | --- |
| Five Practice + five Yoodli materials | Seven top-level material choices, one selected item | long-material browser fixture |
| Choose item in category | Correct material/state, stable focus, no worker | same journey |
| Change slide task / poll | Selected pane retained, edits not lost | rendered deck journey |
| Select slide while editing | Same selector/task; per-slide unsaved edits retained | rendered deck journey |
| Hidden editing/review panes | Available via named keyboard tabs; all existing actions preserved | desk/layout and browser checks |

Compact review verification: all 139 affected desk/layout tests passed (98 desk
journeys updated to use the new task controls, 41 unchanged layout tests). The
real rendered-deck browser journey passed with five synthetic Practice and five
Yoodli items: seven material tabs, correct selected items, retained unsaved text
and pane/focus/caret through refresh, and no additional worker jobs, at 390/1280
px in light/dark. Marketing Studio/Infographic Studio's broader visual journey
also passed at 320/390/768/1440 px, including reduced effects, keyboard dialogs
and enlarged text. It validates synthetic UI behavior, not live artwork quality.
