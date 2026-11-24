# The shared UI kit

Marketing Studio, shared setup, Blog Studio, Presentation Studio, Training Studio and
Infographic Studio draw their pages from one stylesheet, `ui-kit/style.css`, and one shell.
This page records what exists, so a change reuses it instead of drawing a second copy.

Design decisions for new or changed UI come from the `ui-ux-pro-max` skill: accessibility,
interaction, layout, typography and colour. This page does not set a visual direction. It
lists the shared components, and the layout and stylesheet rules that tests check
(`tests/test_layout_pass.py`, `tests/test_ui_consistency.py`). Where a better design needs
one of those rules changed, change the rule, its test and this page together.

Each studio keeps its own colour through `data-product` and `[data-studio]`: Marketing
Studio and Blog Studio blue, Presentation Studio warm orange, Training Studio violet and
Infographic Studio teal. Light and dark appearances have independent tokens.

## The look

All five apps have one look, which began as the liquid pilot on Marketing Studio Home and
Infographic Studio ([its history](liquid-pilot.md)): round, roomy and soft. It is the base
of `ui-kit/style.css`; no page opts into it or out of it, and no stylesheet, page or script
names `data-pilot` (`tests/test_ui_consistency.py`).

| Part | Rule |
| --- | --- |
| Tokens | One set: light in `:root`, dark for this computer's dark and the same dark again when Dark is chosen (`tests/test_css_tokens.py` keeps the two equal). A neutral ground (`#f5f5f7` light, `#141519` dark), white or `#202227` paper, and `--soft-shadow`, `--control-face`, `--face-edge` and `--preview-ground` for the soft surfaces. |
| Cards | `--card-round` 24px corners, `1.5rem` inside (`1.25rem` on a phone), a hairline edge and a very soft shadow. A `.card-title` is the card's heading: ink, `1.1rem`, semibold. |
| Buttons | Pills (`999px`), 44px tall, `.9rem` semibold, on a near-white face with a visible `--control-line` edge. A button inside a `.dialog` keeps `10px` corners. |
| Fields | `.input` has 14px corners and a `--control-line` edge, so its boundary keeps 3:1 against the paper. |
| Shell | A `15.5rem` sidebar with `2rem 1rem` inside; a nav item 46px tall with 14px corners, the current page a tinted pill with an accent bar. A `4.6rem` toolbar. The page starts `2.8rem` below it (`1.6rem` on a phone). On a phone the tab bar has 22px top corners and 49px items. |
| Headlines | `.large-title` is `clamp(2rem, 3.1vw, 2.8rem)`, bold and tight; a `.lede` is quiet with roomy lines. |
| Transient | `.dialog` and `.sheet` have 28px corners, 24px on a phone. |
| Tags | `.tag` is a round, borderless chip on `--well`. |
| Motion | Only something running or waiting moves: a working bead, the arc's light, the line of light, a part being made or the waiting track stage. A status that is simply true is still, such as Infographic Studio's saved infographic, its route's step in hand and its ledger's current revision. |
| Inset | A bordered or filled box keeps its words at least 8px from its edge, and a card or panel 12px or more; a workflow step button has `.75rem` each side. Checked by a look at the screen (`docs/testing.md`). |

`tests/test_ui_consistency.py` holds these values (`test_the_look_is_the_kits_own`) and the motion rule
(`test_only_work_under_way_moves`).

## Layout rules

These rules put each screen in the order a person works. Every studio follows them.

| Part | Rule |
| --- | --- |
| Toolbar | The screen's title (and Back only on a screen reached from another screen, never on a sidebar screen), then at most one filled primary action, then quiet secondary actions. A screen-specific action that is not the primary and has a long name goes under the lede instead. |
| Page header | One sentence in `.lede` saying what the screen is for, then any view-specific secondary actions in a `.bar` beside it. No buttons in a page heading block otherwise. |
| Order | What needs the person first, then work in progress, then ways to start something new, then setup, then finished or archived work. A form runs in the order it is filled; its submit sits at its end. |
| Filters | One row: search first and widest, then choice filters of equal share, then a plain Search button. Rarely used filters go under a **More filters** disclosure. On a phone only search shows, with a **Filters** button that opens the rest and counts those set. Filters apply on change. |
| Selection | A "Select all on this page" check sits on the list heading. A selection bar appears only while something is ticked: the count and how many are out of view, Select all on this page, Select all N matching (through the server, with the same filters), Clear, then the actions with the main one filled. It uses the toolbar material (`.glass`), stays in view below the toolbar on a desktop and sits above the tab bar on a phone. Ticks survive paging and filter changes; say so. |
| Lists | Objects a person opens are opaque cards (`.card`, `.grid`); records compared by columns are a quiet `.table` with one action per row, which becomes a card per row on a phone with its title and action unlabelled. |
| Sheets | Center creation sheets over a dimmed backdrop. Keep forms opaque with consistent rounded edges. Creation uses numbered pages with one current step, Back/Next, and a final Start. The footer stays outside the scrolling form body with one filled action, Save and close, and explicit confirmed discard. Nested sources return focus to their opener with choices kept. |
| Spacing | Cards and sections `1.1rem` apart; a step or field group `0.6rem` inside; one heading level per card (`.card-title`), `.sheet-part` for a section inside a sheet. |
| Long forms and editors | Use named sections or task tabs when a person works on one part at a time. Retain local edits, selection and focus across switches and refreshes. Reveal a hidden invalid field before focusing it. Keep status and the next action visible; put secondary explanations in disclosures. |
| Phone | Toolbar actions wrap under the title; long labels wrap inside their button; every control is at least 44px tall; fixed bars and toasts sit above the tab bar (`--tab-bar-room`) and the page leaves room for them. A page stylesheet uses the kit's breakpoints, `52rem` for the phone and `37.5rem` for a narrow phone. |
| Toasts | Bottom right on a desktop, clear of the sidebar's Search and jump and Appearance; just above the tab bar on a phone. A page may widen them, never move them over the shell. |
| Material | Sidebar, toolbar, sheets, selection bars, Shared settings' save bar and toasts only. Forms, lists, documents and reviews stay opaque, and so does a `.dialog` that holds form fields. |
| Page markup | Every app page reaches under a phone's notch (`viewport-fit=cover`), declares `color-scheme: light dark`, lets the skip link's `<main tabindex="-1">` take the focus, hides `.backdrop` from screen readers, gives every `<button>` a `type`, and (each studio) says in `<noscript>` what it needs. A live region announces a short summary, such as a count, never a whole list or table. |

## The shell kit

One signature, kept to one place: the **progress track**, a project's stages as a single
line in its studio's colour, filled where done, larger where the work is now, and amber
where it waits for the person. Around it the shell stays quiet. `StudioShell`
(`studio_core/deck_web/shell.js`) gives every page the track, Search and jump (Cmd or
Ctrl+K) and the Light, Dark and Auto appearance (one shared setting).
The Home headline is the one place the shell uses the system serif: Marketing Studio's launch
question (`.launch-intro`), a studio's greeting (a `p.large-title` first on its page) and
Infographic Studio's Home (`[data-home]`); every other `.large-title` keeps the plain face.
The serif changes only the face: weight and spacing are those of every `.large-title`.
The appearance is switched by the stylesheet from `<body data-appearance>`, which the server
writes and the shell keeps: Auto follows `prefers-color-scheme`, Light stands it aside, and
Dark applies the same dark tokens. No script reads or rewrites a stylesheet to switch it,
and every `var()` a stylesheet reads names a token one defines (`tests/test_css_tokens.py`).
See the
[design it was built from](../superpowers/specs/2026-11-10-golden-gate-3-design.md).

| Need | Component |
| --- | --- |
| A project's stages | `.track`, `.track-stage[data-state]` (`done`, `current`, `yours`, `todo`, `skipped`), `.track-compact` in a list |
| Search and jump | `.shell-palette`, opened by `StudioShell.palette()`. Each studio, and Marketing Studio's Home, hands it the work its own page lists with `StudioShell.commands(() => [{title, group, hint, keywords, run}])`, asked again each time it opens: group Blogs, Decks, Trainings or Infographics (on Home, the studio's name, with what each row's button says as the hint), the state as the hint, `run` opening the work as its card does, and a Start command for new work. Nothing crosses studios. Put away, it gives the focus back to its opener; a pointer marks a row without scrolling; past 40 results it says how many more there are (`.shell-palette-more`) |
| Appearance | `.appearance-switch` in `.shell-foot`; never a second copy of a token |
| Continue in another studio | `StudioShell.continueLink({id, revision})` gives a studio the home page's link to its own kept Document Library document, or null when it runs alone. The Library (`deck_web/library.js`, with `continueIn`) offers it in a readable document's preview, never on the row: a quiet button, then `.pick-cards` of the installed studios, one that cannot open disabled with what it needs |
| A desk as a workbench | A page part says its zone in `data-zone`: `top`, `parts`, `work-top`, `work`, `rail` or `foot`. From 72rem the page is three columns, the work in the middle, and a part with no zone joins the rail. Narrower, parts follow one another |
| A rail as tall as its own parts | `.workbench-rail` and `.workbench-parts` gather a zone's parts into one. The work and its parts then share a row, `foot` parts follow directly under them, and the rail runs beside all of it (Training Studio) |
| The one arc | `StudioShell.arc({at, yours, finished})`: Brief, Plan, Make, Ship, the same four in every studio; Blog Studio, Presentation Studio and Training Studio draw it from the kit, never by hand |
| A line of light | `.workbench-pulse`, from `StudioShell.pulse('working' \| 'yours' \| 'still')` |
| The one move | `.move-card`, from `StudioShell.move`: the question, what it sets going, one amber action; `calm` where nothing waits. It animates (`.move-card-new`) only when it is a different move, never when it is drawn again |
| A band instead of a rail | `.workbench-top` holding `.workbench-head`, where a desk already pairs its work with a side panel (Blog Studio, a deck's slides) |

### One arc, one workbench, one move

Every studio makes its work the same way, so every desk says it the same way. The arc has
four phases, **Brief, Plan, Make, Ship**; a studio's own steps sit one press below it. The
work itself is the middle of the screen from the first moment. Everything about the
assistant, and the one thing it may need from the person, is in the rail (or the band).
A screen still has one filled button: the move's own action is amber. **F** on a desk reads
the work alone at every width: the parts and the rail step aside, and a quiet
**Show everything** button (`.reading-exit`) held at the foot of the content brings them back,
as F and Escape do. Toasts rise over it (`--foot-lift`).

- **The arc is drawn as a route.** It is the one signature, so it carries the flair: a flat
  band tinted in the studio's colour as far as the work has come (`--arc-reach`), a numbered
  mark for each phase that becomes a tick when done, a line under each name saying what the
  phase is, a dotted line for what is ahead, and, while the assistant works
  (`data-live="true"`, set when the arc has a note), a light that travels the line onward
  from the phase in hand. It stays flat: no material, no shadow.
- **The move does the thing.** Where the next step is one control, the move carries that
  control, so the person never scrolls to find what the card names. Before Blog Studio's
  first check, the move is the check.
- **Make lasts until nothing is left to read or decide.** Reviewing drafts is Make, with the
  note "yours to review". Ship is sending finished work: Training Studio once every material
  is ready, Blog Studio in Finishing.
- **A studio with one status surface keeps it.** Infographic Studio's **Where this stands**
  already holds its route, **Needs you** and its revisions, and no control there shows more
  than twice. It takes the line of light and an amber edge on that card, not a second arc or
  move.
- **Work under way is never amber.** Amber means the person's move. While the assistant
  works, the card in the move's place is `StudioShell.move({working: true, ...})`: the
  studio's colour, what is being done, and that nothing is asked. `.desk-working-note` is
  the studio's colour too.
- **A slow read says so at once.** Bringing in a Google Doc or a page opens a sheet naming
  the steps before the request is sent, and closes itself when the desk opens.
- **A state is not a filled button.** The story in use is a "Selected" tag, each other
  story's **Use this story** is a quiet button that names its story (a choice among peers,
  never a filled one), and Polish on
  Blog Studio's desk is a plain button beside the move.
- **On a phone** the sidebar is the bar of screens, so **Search and jump** and the
  appearance close each page under its content (`.shell-foot-page`).

## Shared components and page stylesheets

`ui-kit/style.css` holds every token, the shell and the controls used by Marketing Studio,
shared setup, Blog Studio, Presentation Studio, Training Studio and Infographic Studio:

| Need | Component |
| --- | --- |
| Shell | `.backdrop`, `.window`, `.sidebar.glass`, `.content`, `.toolbar-wrap`, `.toolbar.glass`, `.page` |
| Actions | `.button`, `.button-filled`, `.button-quiet`, `.button-danger`, `.button-round` |
| Fields | `.field`, `.field-label`, `.input`, `.field-hint`, `label.field`, `.input-typed` |
| Exclusive choices | `.segmented` with buttons or radio `label.seg-option`; five or six options wrap onto rows and fill the chosen one |
| Independent form choices | Native checkbox in `label.check`; use fieldset/legend for a group. A focus ring never substitutes for checked state. |
| Compact marks outside forms | `.chips`, `.chip`, when an explicit pressed state and label explain the mark; use an action button for work that runs immediately. |
| Object choices | `.pick-cards`, `.pick-card`, `.pick-title`, `.pick-says` |
| Steps | `.workflow-steps`, `.workflow-step` |
| Surfaces | `.card`, `.paper`, `.table`, `.callout` |
| Headings | `.large-title`, `.lede`, `.card-title`, `.sheet-part` |
| Status | `.state` with `.bead`, `.tag`, `.toasts`/`.toast`, `.notice` |
| Transient | `.sheet`, `.dialog`, `.menu` |
| A question before an action | `Drafting.confirmInPlace(control, {message, action, keep, danger, place})`: asked beside the control (hidden meanwhile), or at the top of `place` or the page's `<main>` where it has no row; the way out has the focus and gives it back, and a destructive action takes `.button-danger`. One question at a time: asking another answers the open one with its way out. A redraw keeps an open question where it was; one taken off the page unanswered is answered with its way out, so Keep, Escape and anything unanswered never discard. Never a blocking `window.confirm()`, `alert()` or `prompt()` (`tests/test_ui_consistency.py`) |
| Studio mark | `.studio-symbol`, the rounded tile that carries a studio's drawing in its accent colour |
| Studio identity | `[data-studio]` sets `--studio-color` and `--studio-wash`; `.card[data-studio]` takes that studio's colour for its accent, link, focus and hover border |
| Way back | `.suite-link`, the "Marketing Studio" sidebar item a studio shows when Marketing Studio opened it |
| Filters | `.filter-bar` (a `.search` field first), `.more-filters`, `.filters-toggle` |
| Selection | `.panel-heading` with `.select-page`, and `.selection-bar.glass` with `.selection-count` and `.selection-actions` |
| Step row | `ol.intake-progress.intake-guided` from `Drafting.Intake.steps` in `drafting.js`: each step of a start as a button with its name, a tick once complete and what was chosen in it. Every studio's start shows it, whether the shared `pages` draws the sheet or the studio draws its own page |
| Sheet steps | `.create-flow`, `.create-step` (each headed by a `.sheet-part`), `.create-foot`, and the sticky `.sheet-heading`, opaque and reaching the sheet's edges so nothing shows behind it |
| Page | `.stack` (its parts `1.1rem` apart), `.page-head` (the `.lede` and a `.bar` beside it) |
| Ticks | `label.check` with its checkbox; `.research-choices` and `.site-choices` for Research from |
| Desk | `.desk-*` from `drafting.js`: the reading column and aside, part cards, the selection bar, History and the Finishing panel |
| Assistant activity | `.activity-*` from `activity.js`: each running job's "Now:" line and its Show activity disclosure, and the Activity log card; drawn on the card or paper they sit in |

A page stylesheet (`home.css`, `blog.css`, `deck.css`, or an inline style on a static page)
lays out its own parts. It may size and place a shared control, but never draws one, never
styles bare controls or headings for the whole page, and takes every colour from a token.
`tests/test_ui_consistency.py` checks the stylesheets' selectors; a page class on a shared
element is outside what it can see.

The [Cult-inspired workflow implementation](../superpowers/plans/2026-11-07-cult-ui-workflows.md)
records the Training Studio inspector, compact progress, guided steps and grouped
delivery controls. These adapt interaction patterns within the shared vanilla UI kit.

[Actual Cult component ports and provenance](cult-controls.md) cover the shared animated
controls and launcher card surfaces, including reduced-motion and fallback behavior.
