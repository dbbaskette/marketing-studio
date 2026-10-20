# One look and feel across the studio UIs

Approved in chat: every web page in the repository uses one Golden Gate-inspired shell
and one control set. Each product keeps its colour from the Marketing Studio home page:
Blog Studio blue, Presentation Studio orange, Training Studio violet, and Marketing
Studio the system accent. Beyond colour, the pages look and behave alike.

## Why

Blog Studio, Presentation Studio and Training Studio already share the
`ui-kit/style.css` shell: `.window`, a `.sidebar.glass`, a `.toolbar.glass`, `.page`,
sheets, toasts and a bottom tab bar on narrow screens. Two places diverge:

- Marketing Studio home and shared setup rebuild the shell in `home.css`
  (`.workspace-shell`, `.home-sidebar`, `.home-toolbar`). They use global `button`,
  `input`, `label` and `h1`-`h3` rules, hard-coded colours, and a top navigation below
  700 px instead of the shared bottom bar at 52rem.
- Blog Studio's editorial screens and dialogs use an older set: `.primary`/`.secondary`
  buttons, inputs with a `--quiet` border and 12 px radius, and native `<dialog>`
  elements styled apart from the shared sheet.

The Blog Studio beginner page (`studios/blog/preview/blog-studio.html`) and the
unified-settings design preview (`docs/design/unified-settings-preview.html`) each
have their own visual language.

## Approach

`ui-kit/style.css` owns the shell, the tokens and every reusable control. A page's own
stylesheet (`home.css`, `blog.css`, `deck.css`) adds only layout and components that
exist on that page alone. It contains no shell classes and no bare element selectors.
File names stay unchanged, so the static file maps, the local-network allowlist
(`marketing_studio/network.py`) and the packaging link rules
(`core/studio_core/packaging.py`) do not change.

A CSS alias layer was rejected because it keeps two vocabularies that drift again. A
shared JavaScript shell component was rejected as out of proportion: three of the five
pages already match, and every controller's start-up code would change.

## Identity

- `body[data-product]` selects the accent, as it does now. Standalone setup is served
  with the studio's product name and so already takes the studio colour.
- Remove the hard-coded colours from `home.css` (the symbol shadow and the
  `#007aff` profile-review fallback). Every colour comes from a token with light and
  dark values.
- Each studio has one symbol, used on its home card, in its sidebar and in its setup.
  The current glyphs already agree. Marketing Studio keeps its "M" monogram, drawn with
  the shared `.studio-symbol`.

## Shell

Every page uses `.backdrop`, `.window`, `nav.sidebar.glass`, `.content`,
`.toolbar-wrap > header.toolbar.glass` and `main.page`. The sidebar holds the brand, the
navigation and an optional foot line. The toolbar holds the title and the page's
actions. At 52rem and below, the sidebar becomes the shared bottom tab bar, with
safe-area insets.

Navigation items carry an icon and a label in every product. Marketing Studio already
does. The studios add icons for Home, the list screen (Blogs, Decks, Trainings), Status
and Settings, drawn with each controller's existing icon helper.

## Controls

| Need | Shared component |
| --- | --- |
| Actions | `.button`, `.button-filled`, `.button-quiet`, `.button-danger` |
| Fields | `.field-label`, `.input`, `.field-hint`; the existing select and file-picker styles |
| Two to four exclusive options | `.segmented` |
| A choice that is an object (mode, template, material) | One shared choice card, promoted from Presentation Studio's `.pick-card`. It replaces Blog Studio's `.mode-choice` and Training Studio's `.material-choice` styling. |
| Groups and objects | `.card` (opaque) |
| Documents | `.paper` |
| Tabular data | `.table` |
| Page headings | `.large-title` and `.lede` |
| Status | Shared toasts in a polite live region. A message stays long enough to read and pauses while hovered or focused. |
| Errors | The persistent `.notice` with `role="alert"` |
| Sheets and dialogs | The shared sheet look. Blog Studio's native `<dialog>` elements keep their focus and Escape behaviour and take the sheet appearance. |

Material stays on the sidebar, toolbar, sheets, menus and toasts. Forms, cards, tables
and documents stay opaque. The reduced-transparency, increased-contrast,
reduced-motion, no-blur and forced-colours fallbacks in `ui-kit/style.css` cover every
page. The duplicates in `home.css` and `blog.css` are removed.

## Pages

- **Marketing Studio home.** Studio cards are `.card`s: the studio-coloured icon wash,
  name, description, a status chip, then a filled button in the studio colour. The
  settings summary and phone access are cards on the same page.
- **Shared setup**, in Marketing Studio and in each studio. Form sections are cards
  with shared fields. Storage and model routing use `.segmented`. Step progress uses
  `.workflow-steps`, which moves from `blog.css` into `ui-kit/style.css` and so serves
  both setup and Blog Studio's writing steps.
  - On a step or view change, focus moves to the new heading and the change is
    announced.
  - The studio card's accessible name matches its visible button text.
  - When the server stops, the page says so ("Marketing Studio stopped. Run
    `marketing-studio` again.") instead of "Failed to fetch".
- **This computer.** Uses the studios' Status rows (`.computer-item`, `.facts`).
- **Blog Studio desk.** Editorial screens use shared buttons, fields, tables and the
  sheet look. `blog.css` keeps only Blog Studio layouts (task list, workflow steps,
  writing changes, review compare).
- **Presentation Studio and Training Studio.** Adopt the shared choice card and
  navigation icons.
  - Presentation Studio removes the inert `followPointer()` listener.
  - Presentation Studio sizes the storyboard frame as a reading surface: no fixed
    `min(72vh, 48rem)` and no nested scroll area on a phone.
- **Blog Studio beginner page.** Links the shared stylesheet through the in-studio path
  `../skills/blog-studio/assets/management/style.css`, so `studios/blog` stays
  self-contained. It uses the shell and Blog Studio blue, and keeps its content, its
  prompt output and its no-server use.
- **Design documents.** Rebuild `docs/design/unified-settings-preview.html` on the
  shared shell and controls, and regenerate its screenshots. `docs/design/golden-gate.md`
  gains the component inventory and the rule that page stylesheets add layout only.

## Unchanged

Workflows, routes, API calls, authentication, session keys, data and information
architecture are untouched, apart from the setup messages and focus handling listed
above. Fonts remain the system stack, and no font is distributed. There is no build
step and no new dependency.

## Verification

- A guard test fails if a stylesheet outside `ui-kit/` styles shell classes
  (`.window`, `.sidebar`, `.toolbar`, `.nav-item`, `.button`, `.input`, `.card`,
  `.sheet`) or bare elements (`button`, `input`, `select`, `label`, `h1`-`h3`).
- Run the existing suites:
  - Root: `tests/test_suite.py`, `tests/test_home.py` and the remaining root suite.
  - Presentation Studio and Training Studio page harness tests, including Training
    Studio's contrast check.
  - Blog Studio: `check-newcomer.cjs` and `check-management.cjs`.
  - The studio package validators.
- Render every page with synthetic data at desktop and phone widths, in light and dark
  appearances. Compare the shell, controls and states across products.
- Socket-based tests, `scripts/ci/check.sh` and the Tart runner are run where local
  ports are available.
