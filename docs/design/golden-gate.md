# Golden Gate-inspired studio UIs

Marketing Studio, shared setup, Blog Studio, Presentation Studio and Training
Studio use one restrained visual language through `ui-kit/style.css`. Use the
`macos-golden-gate-design` skill when available and keep the existing web stack.
This is a CSS approximation, not native system material or physical refraction.
Navigation and toolbar material use diffuse blur, a soft light edge and a subtle
cool tint. These highlights belong to the shell; the canvas stays neutral.

Marketing Studio uses blue for selected navigation and the system accent, when
available, for shared actions. Blog Studio uses
blue, Presentation Studio uses warm orange and Training Studio uses violet on
launch icons and buttons. The same identity follows into each native studio's
sidebar symbol, navigation, primary actions and selected controls through its
`data-product` attribute and the linked shared stylesheet. Each identity has
independent light and dark tokens.
Status words and dots retain semantic colors, and studio identity never replaces
the visible product name. Selection has both a stronger label and a bounded fill.

| Surface | Treatment |
| --- | --- |
| Sidebar and unified toolbar | Subordinate neutral material, modest diffusion, shared pane boundaries |
| Forms, documents, reviews and data | Opaque content/paper tokens, readable text and quiet separators |
| Selected navigation or choices | Explicit selected state, accent and tighter rounded highlight |
| Studio launch cards and slide choices | Meaningful object boundaries, opaque fill, restrained border |
| Sheets, menus and toasts | One elevated surface with existing keyboard/dismissal behavior |
| Status and errors | Existing words and state shapes; semantic colors remain informative |

The shell meets the viewport edges. Ordinary content does not float inside an
extra rounded app window. Avoid per-row glass, wallpaper washes, repeated shadows
and pointer-following highlights. Keep material tokens separate from opaque
content tokens. Preserve current brand identity and use the existing system font
stack without distributing fonts.

Shared tokens define independent light and dark appearances. Existing contrast
checks cover text, selected states, focus rings and semantic status colors.
Reduced transparency and increased contrast use solid surfaces and stronger
boundaries; reduced motion disables movement. When backdrop filtering is absent,
the opaque fallback retains the same layout and controls.

The native bottom navigation remains available at narrow widths. Shared setup
reflows field grids and keeps controls consistently sized. Long paths must wrap
within the pane rather than widening the viewport. Keep existing workflow,
authentication, source permissions and approval behavior unchanged in visual work.

The unified-settings HTML file in this directory is a design preview using
synthetic in-memory data. It shares this visual direction; its profile routing,
global limits and override interactions do not imply those pending backend
features are already implemented.

## Shared components and page stylesheets

`ui-kit/style.css` holds every token, the shell and the controls used by Marketing Studio,
shared setup, Blog Studio, Presentation Studio and Training Studio:

| Need | Component |
| --- | --- |
| Shell | `.backdrop`, `.window`, `.sidebar.glass`, `.content`, `.toolbar-wrap`, `.toolbar.glass`, `.page` |
| Actions | `.button`, `.button-filled`, `.button-quiet`, `.button-danger`, `.button-round` |
| Fields | `.field`, `.field-label`, `.input`, `.field-hint`, `label.field`, `.input-typed` |
| Exclusive choices | `.segmented` with buttons or radio `label.seg-option` |
| Independent choices | `.chips`, `.chip` |
| Object choices | `.pick-cards`, `.pick-card`, `.pick-title`, `.pick-says` |
| Steps | `.workflow-steps`, `.workflow-step` |
| Surfaces | `.card`, `.paper`, `.table`, `.callout` |
| Headings | `.large-title`, `.lede`, `.card-title`, `.sheet-part` |
| Status | `.state` with `.bead`, `.tag`, `.toasts`/`.toast`, `.notice` |
| Transient | `.sheet`, `.dialog`, `.menu` |

A page stylesheet (`home.css`, `blog.css`, `deck.css`, or an inline style on a static page)
lays out its own parts. It may size and place a shared control, but never draws one, never
styles bare controls or headings for the whole page, and takes every colour from a token.
`tests/test_ui_consistency.py` checks the stylesheets' selectors; a page class on a shared
element is outside what it can see.

![Marketing Studio home](unified-settings-home.jpg)
![Shared settings, models](unified-settings-models.jpg)
![Presentation Studio](golden-gate-presentation.jpg)
