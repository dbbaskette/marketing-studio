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
[design it was built from](../archive/superpowers/specs/2026-11-10-golden-gate-3-design.md).

| Need | Component |
| --- | --- |
| A project's stages | `.track`, `.track-stage[data-state]` (`done`, `current`, `yours`, `todo`, `skipped`), `.track-compact` in a list |
| Search and jump | `.shell-palette`, opened by `StudioShell.palette()`. Each studio, and Marketing Studio's Home, hands it the work its own page lists with `StudioShell.commands(() => [{title, group, hint, keywords, run}])`, asked again each time it opens: group Blogs, Decks, Trainings or Infographics (on Home, the studio's name, with what each row's button says as the hint), the state as the hint, `run` opening the work as its card does, and a Start command for new work. Nothing crosses studios. Put away, it gives the focus back to its opener; a pointer marks a row without scrolling; past 40 results it says how many more there are (`.shell-palette-more`) |
| Appearance | `.appearance-switch` in `.shell-foot`; never a second copy of a token |
| Continue in another studio | `StudioShell.continueLink({id, revision})` gives a studio the home page's link to its own kept Document Library document, or null when it runs alone. The Library (`deck_web/library.js`, with `continueIn`) shows it in a readable document's preview, never on the row: `.pick-cards` of the installed studios, in view with the preview, each opening its studio in one press. One that cannot open stays a card, `aria-disabled` (never the native disabled state, which dims) with a `.tag` naming its state and its reason in full-strength words |
| A desk as a workbench | A page part says its zone in `data-zone`: `top`, `parts`, `work-top`, `work`, `rail` or `foot`. From 72rem the page is three columns, the work in the middle, and a part with no zone joins the rail. Narrower, parts follow one another |
| A rail as tall as its own parts | `.workbench-rail` gathers the rail's parts into one. The work and its parts then share a row, `foot` parts follow directly under them, and the rail runs beside all of it (Training Studio) |
| The one arc | `StudioShell.arc({at, yours, finished})`: Brief, Plan, Make, Ship, the same four in every studio; Blog Studio, Presentation Studio and Training Studio draw it from the kit, never by hand |
| A line of light | `.workbench-pulse`, from `StudioShell.pulse('working' \| 'yours' \| 'still')` |
| The one move | `.move-card`, from `StudioShell.move`: the question, what it sets going, one amber action; `calm` where nothing waits. It animates (`.move-card-new`) only when it is a different move, never when it is drawn again |
| A band instead of a rail | `.workbench-top` holding `.workbench-head`, where a desk already pairs its work with a side panel (Blog Studio, a deck's slides) |
| The parts of a project | `StudioShell.parts({label, groups, chosen, choose, key})`, the one list of an open project's parts down the left of its workbench; see [The parts of a project](#the-parts-of-a-project) |
| A workbench with no rail | A desk with parts and work and nothing for a rail (its band is on top: Presentation Studio) gives the rail's room to the work |

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

### The parts of a project

Every studio's project page lists the open project's parts in one place, built by one
function, so a person always sees what exists, what state each part is in and which one is
in front of them. It is drawn only by the kit (`ui-kit/style.css`, "the parts of a
project") and behaves only as `StudioShell.parts` does (`core/studio_core/deck_web/shell.js`,
which every studio page already loads); a studio hands it data and one callback and draws
nothing of its own for it.

```js
const nav = StudioShell.parts({
  label: 'Parts of this training',          // the <nav>'s name: "Parts of this deck|draft|infographic"
  key: 'desk-parts',                         // optional; what its controls are known by (data-key)
  groups: [                                  // in order; a group with no parts is left out
    { title: 'Level 101', parts: [
      { id: 'guide', name: 'Guide', state: 'Draft' },
      { id: 'deck', name: 'Deck', state: 'Writing' },           // busy: moves, as only work under way does
    ] },
    { title: 'Behind it', parts: [{ id: 'sources', name: 'Research & sources', count: '3 sources' }] },
  ],
  chosen: 'guide',                           // the id of the part shown in the middle
  choose: (id) => { /* show it, keep it in the address, draw the page again */ },
});
```

**Inputs.** A part is `{id, name, state, count, busy}`. `id` is any string unique in the
list; `name` is the words the part is called by. `state` is one word of the vocabulary below,
or nothing: any other word is not shown. `count` is a short phrase about supporting material
("3 sources", "4 slides"), shown only where there is no state. `busy` marks the part as being
made, the one thing in the list that moves; it is true for Writing unless said otherwise.

**What it returns.** A `<nav class="parts" data-zone="parts" aria-label="label">`, placed
as a direct part of the page like any other zone. It holds a `.parts-toggle` button and a
`.parts-list`: each group a visible `h2.parts-group-title` and a list of `button.parts-item`
(`type="button"`), each showing its name (`.parts-name`) and its state or count
(`.parts-state[data-state]`), with a hidden comma between so a screen reader hears the name,
then the state ("Guide, Draft"). The part shown carries `aria-current="true"`.

**Behaviour.**
- From 72rem it is the workbench's left column (13rem), held in view beside the work as the
  page scrolls and no taller than the window. Narrower, the `.parts-toggle` above the work
  names the part shown, its group when there are several (`Level 201: Guide, Draft`,
  otherwise `Showing: Section 2, 3 slides`), and opens the same list under it in the page's
  flow: never a sheet over the work and never a sideways scroll.
- Tab enters the list at the part shown (the only item with `tabIndex` 0); Up and Down move
  part by part across groups, Home and End go to the first and last; Enter or Space chooses.
  Escape closes the narrow list and gives the focus to its control.
- `choose(id)` is called for every part chosen, the one shown too (a studio whose page is one
  column brings it back into view). After it returns, the focus stays on the part chosen as
  the page draws it again, or on the narrow control when the list was opened from there,
  unless `choose` moved the focus somewhere of its own (a heading, say), where it stays.
- A list open on a narrow screen stays open when it is drawn again with the same `key`, so a
  refresh never closes it. Drawing it again is the studio's to do, on every change: the
  component keeps no other state.
- Reading alone (F) hides it with the parts zone at every width.

**The studio's side.** The studio shows the part chosen in the middle, keeps it in its own
address (choosing a part adds a history entry, so Back returns to the part before; a reload
opens the same part; a poll or refresh only says again what is shown), and replaces with the
list any control that listed the same parts. A control that switches views of one part stays
inside that part.

**States: one vocabulary.** Each word means the same in every studio, and its tint only
repeats what the word says; the longer sentence a studio shows today stays on the part itself.
Where a studio has no state for a part, it shows none (or a count) rather than invent one.

| Word | Meaning | Tint (`data-state`) |
| --- | --- | --- |
| Writing | The assistant is making or remaking it now; the only state that moves | studio colour (`working`) |
| Queued | It will be made after what is being made now | quiet (`queued`) |
| Needs you | It waits on the person: a decision, an approval, a fix, a change not saved | amber (`yours`) |
| Draft | Made, not yet marked ready | quiet (`draft`) |
| Ready | The person marked it ready | green words (`done`) |
| Out of date | Made from something that has changed since | red (`stale`) |
| Left out | The person chose to leave it out | quiet (`out`) |

**Per studio.**

| Studio | Groups and parts | State mapping | Replaced controls, and where they live now |
| --- | --- | --- | --- |
| Training Studio | One group per level ("Level 101"; "Materials" without levels) with its materials in order: Plan, Guide, Brief, Deck, Practice, Yoodli; several scenarios or Yoodli layouts of a level are one part ("Practice · 3") with its picker inside it. Behind it: Research & sources, counting the research's sources | writing Writing, queued Queued, decide and needs Needs you, held Out of date, draft Draft, ready Ready (left-out materials are not listed, as before). A part of several materials says the most pressing of theirs | The level switch and the material tabs: both are the list. "Open research & sources", the needs line's jumps and the Mark-ready sheet's Open choose a part through it. The scenario picker stays inside Practice |
| Presentation Studio | Deck: the Outline (where the deck has one), then each section ("Section 1", or the kind of the deck's opening and closing slides; a deck of your own at Selected changes is one part, "Slides"), its slides shown in the middle at the slide kept, else its first | A section says Writing while one of its slides is drawn again, Needs you while one blocks delivery or waits on the person, otherwise its count of slides: the desk has no approval to call Ready. The Outline says Needs you while a change on it is not saved | The Slides and Outline tabs. The navigator of slides stays, as the way between the slides of the deck; Sources and research stay beside the slides and the look in the Outline, where they were |
| Blog Studio | Draft: the Outline, then the Title, the Opening and each section by its heading, the part shown in Read, Edit section or Edit everything. Finishing: each tool with something open ("Copy edit · 3"). Behind it: Sources, counting the blog's sources, brought into view beside the draft (Finishing put away first; on a phone, their fold opened) | A draft part or the Outline says Writing while a job changes it; nothing else, as the desk has no state per part. A Finishing tool says Needs you while its suggestions wait, Writing while it runs, and the GEO review Out of date once the post changed since it ran | The Draft and Outline tabs, Go to section, the Outline button and the row of suggestions to review: all are the list. Read, Edit section and Edit everything stay, as views of the part shown; Add a source stays in the view's tools and beside the draft. Review mode is its own screen, left with Back, without the list |
| Infographic Studio | Infographic: Story, Page, Artwork, Review and checks, Saved files; Behind it: Brief, Sources and facts (counting its sources), History; each listed where the page shows it now. The page stays one scrolling column: a part chosen comes into view, opened, its heading focused. Until 90rem what sat in the rail follows the page in its column | Writing while work on that part runs (Finding the story; Building, Repairing or Updating the page; art direction and artwork; inspecting and the review; preparing and delivering files). Out of date from the page's own marks (facts on Sources and facts, the story, the page, the artwork). Needs you while the story waits to be chosen, or the page to be reviewed or approved. The page Draft once built, Ready once approved | Nothing: the page had no switch of parts. Where this stands, the toolbar's next step and every disclosure stay where they were. The part chosen is kept in the tab's history state, never in the address's fragment |

`tests/test_ui_consistency.py` (`PartsListTests`) holds the kit's side: drawn once, before the
desk's parts, opaque, every control at least 44px, only a part being written moving and still
under reduced motion, one control and no sideways scroll below 72rem. `tests/shell_page_check.js`
drives the behaviour; each studio's page suite checks its own list, its states and its address.

Where a studio's work has its own side panel (Blog Studio's sources and Finishing, Infographic
Studio's word inspector or rail), the list takes the room first: from 72rem the panel follows the
work, and sits beside it again only where there is room (Blog Studio from 90rem; Infographic
Studio's rail from 90rem and its inspector from 112rem). Each studio's stylesheet places this, and
`tests/test_ui_consistency.py` names Blog Studio's placements of the desk's parts.

## Shared components and page stylesheets

`ui-kit/style.css` holds every token, the shell and the controls used by Marketing Studio,
shared setup, Blog Studio, Presentation Studio, Training Studio and Infographic Studio:

| Need | Component |
| --- | --- |
| Shell | `.backdrop`, `.window`, `.sidebar.glass`, `.content`, `.toolbar-wrap`, `.toolbar.glass`, `.page` |
| Actions | `.button`, `.button-filled`, `.button-quiet`, `.button-danger`, `.button-round` |
| Fields | `.field`, `.field-label`, `.input`, `.field-hint`, `label.field`, `.input-typed` |
| Exclusive choices | `.segmented` with buttons or radio `label.seg-option`; five or six options wrap onto rows and fill the chosen one. The same control is a tablist when the choice switches a panel: `role="tablist"` with `role="tab"` options, the chosen one `aria-selected="true"`, drawn as a pressed segment is |
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

The [Cult-inspired workflow implementation](../archive/superpowers/plans/2026-11-07-cult-ui-workflows.md)
records the Training Studio inspector, compact progress, guided steps and grouped
delivery controls. These adapt interaction patterns within the shared vanilla UI kit.

[Actual Cult component ports and provenance](cult-controls.md) cover the shared animated
controls and launcher card surfaces, including reduced-motion and fallback behavior.
