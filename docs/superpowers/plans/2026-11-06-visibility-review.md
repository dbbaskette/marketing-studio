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

## Settings sections and Quick scan — #406

Shared settings shows one named section, retaining all inputs and unsaved changes
in the form. First-run setup keeps its existing three steps. Validation and stale
form conflict handling reveal the affected section before focusing the control.
Training Studio Change settings separates Teaching, Materials and Research; the
review/save decision remains explicit with the existing revision check.

Quick scan gets callout padding, bottom-aligned controls and a short effective
model/reasoning line. Its main explanation describes the benefit and when the
choice applies; implementation targets/caveats move out of the main form. Keep
further behavior behind a disclosure. Save/review controls remain reachable.

| State / action | Expected result | Regression |
| --- | --- | --- |
| Edit one section, visit another, return | Values unchanged, no save/job | settings browser |
| Invalid hidden field | Open its section and focus the field | settings browser/native checks |
| Review Training Studio changes | Review consequences alone, edit/back retains section | settings journey |
| Save/reload or stale shared form | Existing persistence/conflict contract retained | shared settings suite |

Settings verification: 65 shared UI/layout/settings checks and 72 Training Studio
settings/layout checks passed. Real shared-settings phone/desktop journeys passed
section switching with unsaved edits, one visible section, aligned/padded Quick
controls, save/reload and revealing a hidden invalid repository field. The
Training Studio journey passed hidden scenario validation, review/save/reload,
return to AI choice and unchanged worker attempts/spending. The sheet's separate
phone/desktop check passed scroll ownership, visible actions, focus trapping,
Escape/return and zero changes on Cancel. Test DOM expectations were updated for
section visibility; save/conflict assertions were retained.


## US English authoring — #408

The supplied slide contained “practise” because Training Studio's author-facing
handoff and examples used it. Add a common US English default to authored guidance
and the provisional outline; honor an explicit creator language/locale request.
Correct the seeding examples and prompt text. Keep quotes, code, names, approved
slide wording and existing saved materials intact. Verify assembled briefs and
outline/deck handoffs with fake workers; this is prompt guidance, not a claim that
every future model output is deterministically spell-checked.

US English verification: all 38 brief/outline checks and 25 deck handoff/delivery
rule checks passed. Existing files were not rewritten and no provider was called.
