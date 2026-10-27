# Piece 4, the layout pass: design

**Date:** 2026-10-26, at main cc53056. **Owner's words:** "Lets apply our UI changes to blog
studio to the other studios. We also need to do an audit of workflow and clean it up", and,
asked whether that meant the layout rules or the writing desk as well: "1 and 2".

This is piece 4 of `2026-10-26-workflow-audit.md`. It applies the Layout rules in
`docs/design/golden-gate.md` to Presentation Studio, Training Studio, and Marketing Studio's
home and shared setup (`core/studio_core/setup_web/*`). It does it the way Blog Studio's
layout pass did (PR #98, `studios/blog/docs/superpowers/specs/2026-10-23-library-voices-and-layout-design.md`):
one primary per toolbar, a one-sentence lede, content in the order a person works, filter
rows and a selection bar on lists, numbered sheets for what makes something, and a table of
every control that moved.

The shared components come first. The filter row, the selection bar, the numbered sheet
steps, the sticky sheet heading, page spacing and the research choice live only in Blog
Studio's `blog.css` today. They move into `ui-kit/style.css`, Blog Studio switches to them
with nothing a person sees changed, and then the other studios use them.

Pieces 1 to 3 merge before this one. Piece 1 changes words; this piece names controls by
what they do and where they live. Where piece 1 changed a sentence quoted here, keep piece
1's words, cut to one sentence where the rule needs one.

## What is wrong now

Line numbers are at main cc53056. They were checked against the code for this spec.

### The shared components live in Blog Studio's stylesheet

- The filter row is `.filter-bar`, `.filter-bar .search`, `.more-filters`, `.filters-toggle`
  and the phone rule that shows only search (`studios/blog/skills/blog-studio/assets/management/blog.css:21-30`,
  `:136-139`).
- The selection bar is `.library-selection`, `.selection-count`, `.selection-actions`,
  `.panel-heading .select-page` and its phone placement (`blog.css:118-135`). Its name ties
  it to one screen.
- The numbered sheet steps are `.create-flow`, `.create-step` and `.create-foot`
  (`blog.css:148-153`), drawn by `sCreateStep` (`runner.js:641`).
- The sticky sheet heading is `.sheet-heading` (`blog.css:91-93`).
- Page spacing is `#studio-page>*+*{margin-top:1.1rem}` (`blog.css:16`). Marketing Studio
  repeats it by id: `#home > * + *, #settings > * + *, #computer > * + *, .setup-form > * + *`
  (`core/studio_core/setup_web/home.css:134-139`).
- The research choice is `.research-choices` and `.site-choices` (`blog.css:110-116`), with
  the tick label `.check` (`blog.css:44`). Presentation Studio (`researchFromField`,
  `desk/app.js:3057`) and Training Studio (`researchFields`, `desk/app.js:4328`) draw the same
  choice again, as chips.
- The page header beside the lede is `#editorial-screen>.view-head` (`blog.css:18-19`).

Every studio's `style.css` and `markdown.js` is a symlink to `ui-kit/` (Git mode 120000, for
example `studios/training/skills/training-studio/scripts/desk/style.css -> ../../../../../../ui-kit/style.css`).
`core/studio_core/packaging.py:23` allows exactly those links and materializes them in
bundles. The training audit's "byte-identical copy" note describes the files a bundle holds,
not the checkout, so there is nothing to re-sync. Blog Studio's
`assets/management/training-studio-ui.json` still pins `style.css` at a hash that no longer
matches (`8730278…` against `03ecdf1…` now) and names the retired `training-studio`
repository; `docs/marketing-studio-spec-and-plan.md:130` already calls it retired.

### Controls under 44px, and a bar under the tab bar

- `ui-kit/style.css`: `.link` `min-height: 1.75rem` (:614), `.seg-option` `2.3rem` (:675),
  `.menu-item` `2.4rem` (:715), `.input` `2.7rem` (:1279), the file picker's button `1.9rem`
  (:1314), `.chip` `2.4rem` (:1341). 44px is 2.75rem.
- Both deck studios put every toolbar action but the filled one into a "More" menu on a
  phone (`foldActions`, Presentation `desk/app.js:633-640`, Training `desk/app.js:755-770`),
  so those actions become 2.4rem `.menu-item`s. The rule says toolbar actions wrap under the
  title.
- `.review-bar` is `position: sticky; bottom: 0; z-index: 1` (`ui-kit/style.css:2760-2768`).
  On a phone the tab bar is `.sidebar`, fixed at the bottom with `z-index: 6`
  (`:2204-2217`). The bar that sends every marked request in Training Studio's combined
  review, and the tally of Presentation Studio's item-by-item stop, sit under Home, Trainings,
  Status and Settings.

### Presentation Studio (`studios/presentation/skills/presentation-studio/scripts/desk/app.js`)

- **Toolbars.** `toolbar(spec)` (:1040) places `spec.actions` in the order given. Home passes
  `actions: [start, lead]` (:1491), so the quiet "New deck" comes before the filled
  "Review <title>". The deck screen passes Approve, "Ask for changes" (a plain button),
  Pause (plain), Stop (quiet), Resume and "Undo the last step" (`deckActions`, :5679-5724).
- **Ledes.** Home has none; it opens with a `.large-title` greeting (:1478). Decks, Status
  and Settings have none. The deck screen puts the now-line and the state before its
  `.lede` (`deckIntro`, :3540-3542), and three more sentences follow. The set-up lede is
  three sentences: "Check this computer, say where your team keeps its decks, and choose what
  a new deck starts with. Each answer is checked as you give it, and nothing is changed until
  you save." (:2549-2551). Published's lede is two (:6950-6952).
- **Order.** Home draws `['updates', …, updatesCard]` before "Needs you" (:1479-1480). The
  deck screen draws the intro, the note box, the "Where it is" timeline, team notices, the
  problem, the worker's question, then the gate (:5741-5762); Delivered and "Slides taking
  shape" come after the gate, and Hand over and Delete last. Status's filled primary is
  "Check this computer", but its result card is the last part (:1691-1697).
- **Lists.** Decks has one search box applied as each key is typed, "Find a deck" (:1528-1532),
  no choice filters and no Search button. Delete is one card at a time (`deleteButton`,
  :6094). Published is rows in a card ("Published decks", :6953).
- **Forms that make something.** "New deck" is a full-page wizard (`paintNew`, :3191-3220):
  route cards (`routeStep`, its lede a question, "How does this deck begin?", :2723), then two
  or three pages (`NEW_STEPS`, :133-137) with "Step 1 of 3" above the title and a foot of
  "Back a step" or "Another way to begin" with Continue or "Start the deck". There is no
  Cancel. The last page puts the brand first, then a closed "Options" card, then "Where this
  deck stops", then an aside (:3183-3188). "Bring in a deck" is a list of action buttons with
  a Cancel and no submit (:1558-1580). The picture form in an outline row has no Cancel
  (:4469-4478).
- **Headings.** "Review the direction" holds the research panel and the look panel as cards
  inside a card (`outlinePanel`, :4555-4566); its research request is a bare textarea in a
  `<details>` with only an aria-label and no Cancel (:4568-4578). Panels add `h3` and `h4`
  sub-headings. List rows are `h3.row-title` inside a card with an `h2.card-title` (:1402),
  deck cards are `h2.row-title` (:1502).
- **Settings.** Ten cards (:1727-1744). "Shared settings" leads to `/onboarding/`;
  "What a new deck starts with" → "Change them" (:1718-1724) and Workspace's "Change the
  set-up" both lead to Set-up. "Turn on notifications" is filled (:1710).
- **Phone.** The item-by-item stop's send is only in the toolbar: "The one button that sends
  the marks is the toolbar's" (:5452-5453), far above the review bar the tally sits in.
- **Spacing.** `deck.css` uses 0.35, 0.55, 0.6, 0.7, 0.8 and 0.9rem (`deck.css:7-124`).

### Training Studio (`studios/training/skills/training-studio/scripts/desk/app.js`)

- **Toolbars.** Home passes `actions: [start, lead]` (:1748); Trainings passes Published
  then New training (:1789-1791). Gates pass Ask for changes (plain), More, then the filled
  Approve (`gateActions`, :2478-2513). The run screen's Pause, Resume, "Review X" and "Open
  the index" are plain; only Stop is quiet (`runActions`, :5772-5807).
- **The combined review.** The toolbar's filled "Approve the first drafts" stays filled after
  items are marked "Needs changes"; the action the person is taking, "Send N requests", is a
  plain button in the bar (`reviewBar`, :6204-6235). The card carries its own `.lede`
  (:6242), so the screen has two. "Looks good" exists only on a phone (`if (small)`, :6348);
  a desktop reader cannot mark an item looked at, though the bar counts "N of M looked at".
- **The run screen's order.** Part order puts the combined review above a worker's question
  (:6394-6452). A deck that waits for a picture asks for it in a four-field form inside a row
  of the deck card ("Supply the picture", "What it shows", "Where it came from", "Any limit on
  its use, if there is one", plain "Add the picture", `assetForm`, :5948-5966). A Google
  copy conflict ("Use the Doc's version" / "Keep this version and send it", :5563-5564) sits
  in Copies, after Workers and Steps. "Use this look" is filled even beside a problem's
  filled action.
- **New training.** `paintNew` (:4703-4735) shows "Continue" or "Start the training" only
  in the toolbar (`actions: [go]`, :4730); the form's own submit is hidden ("A native submit
  inside the form preserves Enter while the visible action stays reachable in the existing
  toolbar on a phone", :4717-4719). Step 3, "Review and start", shows the "Ready to start"
  summary first, then new inputs: where it stops, sources, the assistant and limits. No step
  has a `.lede`.
- **Gates.** A `.lede` is drawn only for a scenario's ownership or a deck's pictures
  (:2530-2532). A gate a combined review covers has no toolbar action; the way out is a plain
  "Request changes in the …" in a callout (:2416-2418).
- **Home.** "Updates" and "Your other studios" come before "Needs you" (:1735-1736); the
  greeting is a `.large-title`; there is no lede and no way to start besides the toolbar.
- **Lists.** Trainings, Published and Status have no filters. Cards title with
  `h2.row-title` (:1757); rows in a card are `h3.row-title` (:1613, :1639).
- **Detail, Status, Settings, Index.** Training detail draws Files before "In the way", and
  draws "In the way", "Left out or limited" and "Warnings" even when empty (`paintTraining`,
  :3071-3111). Status's "This computer" card is last (:2009). Settings has no lede, a filled
  "Turn on notifications" (:2039), and "See the versions" in two cards (:8070, :8097). The
  index has no lede and "Download the index" is a quiet button under the document
  (`drawIndex`, :8214-8215).

### Marketing Studio home and shared setup (`core/studio_core/setup_web/`)

- **One step, three titles.** In first-run setup the step shows the workflow step "Your
  workspace" (`index.html:44`, `app.js:36`), the large title from `labels[step]`
  (`app.js:92`) and the card title "Where your work lives" (`index.html:69`); step 1 shows
  "You and your assistant" three times, plus "Step 1 of 3" (`app.js:94`).
- **Sheet headings in cards.** `h4.sheet-part` "Models for your work", "Review level", "Where
  is your brand skill?" and "Delivery and previews" sit inside cards (`index.html:55,64,80,94`);
  each model profile is a `paper` with `h5.sheet-part` (`app.js:268`); This computer's items
  are `h4.row-title` (`app.js:493`).
- **Two saves.** "Save settings" ends the form (`index.html:109`); the "Studio installations"
  card follows with its own "Save installation folders" (`index.html:111`). Installation
  folders are kept in Marketing Studio's own state (`marketing_studio/page.py:121-130`), not
  in the studios-config file.
- **Ledes.** Home: "Your settings are shared. Each studio has its own space to work."
  (`index.html:30`). This computer: "Check the tools available to your studios. Each studio
  checks sign-in when you use it." (`index.html:114`). Setup: "Set up once. Your studios will
  start with these choices." (`app.js:93`).
- **This computer's one action** is a filled "Check computer" under the list
  (`index.html:115`), not in the toolbar.
- **Connect.** A studio that needs "Connect" (`app.js:340`) shows it as a plain button below
  the status, while "Open <Studio>" stays filled.
- **The page stylesheet draws shared controls.** `.studio-icon` (`home.css:28-41`) draws the
  tile ui-kit has as `.studio-symbol` (`ui-kit/style.css:369`); `.studio-status::before`
  (`home.css:65-72`) draws a dot where `stateLine` (`app.js:71-75`) already uses
  `.state`/`.bead`, so one card shows two dot styles; `.site-row` (`home.css:311-318`) draws a
  ruled list instead of `.table`.
- **Spacing.** `.studio-list` gap `1rem` (`home.css:18`); `.setup-part > * + *`,
  `#model-profiles`, `.setup-more`, `#brand-choices`, `.profile-card` and `.profile-explicit`
  use `0.8rem` (`home.css:157-162`, `:205-208`); `.profile-cards` gap `0.8rem` (`:197`).

## The design

### 1. The shared components move into `ui-kit/style.css`

Each rule moves with the same values, so Blog Studio looks the same.

| Need | Was (blog.css or home.css) | Now (ui-kit) |
| --- | --- | --- |
| Filter row | `.filter-bar`, `.filter-bar .search`, `.filter-bar>.field:not(.search)`, `.more-filters`, `.more-filters>summary`, `.more-filters>.field`, `.filters-toggle`, phone rules | Same names |
| List heading with Select all | `.panel-heading`, `.panel-heading .select-page` | `.panel-heading`, `.select-page` |
| Selection bar | `.library-selection`, `.selection-count`, `.selection-actions`, phone placement | `.selection-bar`, `.selection-count`, `.selection-actions` |
| Room for the bar on a phone | `#editorial-screen:has(.library-selection:not([hidden])) .footnote{padding-bottom:12rem}` | `.content:has(.selection-bar:not([hidden]))` leaves `12rem` at the foot |
| Numbered sheet steps | `.create-flow`, `.create-step`, `.create-step:first-child`, `.create-step>*+*`, `.create-foot` | Same names |
| Sticky sheet heading | `.sheet-heading` and its two child rules | Same names |
| Page spacing | `#studio-page>*+*`; `#home`, `#settings`, `#computer`, `.setup-form > * + *` | `.stack > * + * { margin-top: 1.1rem }` |
| Page header | `#editorial-screen>.view-head`, `>.lede` | `.page-head` (lede grows, a `.bar` beside it) |
| Research choice | `.research-choices`, its `legend`, `[hidden]`, `.site-choices`, `.site-choices .check span` | Same names |
| A tick with its label | `.check`, `.check input` | Same names |
| Launch card tile | `home.css` `.studio-icon` | `.card[data-studio] > .studio-symbol`: the studio's wash and colour, no lift |

A page stylesheet may still size and place these. `docs/design/golden-gate.md`'s component
table gains rows for them. `tests/test_ui_consistency.py` adds them to `COMPONENTS` and
`SHARED`, so a page stylesheet can no longer draw them, and adds
`core/studio_core/deck_web/deck-panels.css` to `PAGE_STYLES` (its literal fallback colours,
such as `var(--paper, #fff)`, lose the fallback).

### 2. Blog Studio switches over, with nothing changed

- `index.html`: `#library-selection` takes `selection-bar glass` in place of
  `library-selection glass`; `#studio-page` takes `class="stack"`; the view head takes
  `page-head`. Element ids stay, so `check-management.cjs` and the routes are untouched.
- `blog.css` loses every moved rule. Blog-only rules that name a moved class are rewritten
  to the new name (`.view-library` rules stay).
- Blog Studio's own Home rows keep `h3.row-title` and its Home toolbar keeps New blog before
  Review. Both differ from what this piece does in the other studios; they are listed under
  "Decisions for the owner", not changed here.
- `training-studio-ui.json` is deleted with its line in `references/package-notes.md:26`,
  unless piece 2 has deleted it. The links it records are now the suite's own.

### 3. Every control 44px, and bars above the tab bar

- `ui-kit/style.css`: `.seg-option`, `.chip`, `.menu-item` and `.input` take
  `min-height: 2.75rem`. Inside the 52rem phone query, and for `(pointer: coarse)`, `.link`
  becomes `display: inline-flex; align-items: center; min-height: 2.75rem`, and the file
  picker's button `min-height: 2.75rem`. On a desktop a `.link` inside a sentence keeps its
  line height.
- The phone query defines `--tab-bar-room: calc(4.4rem + env(safe-area-inset-bottom))`, the
  height the tab bar takes. `.review-bar` sticks at `bottom: var(--tab-bar-room)` with
  `z-index: 4`, under the toolbar (5) and the tab bar (6), above the page. `.selection-bar`
  is fixed at the same `bottom`.
- Blog Studio's controls grow by up to 0.45rem where they were shorter. That is the only
  change a Blog Studio user can see in this piece.

### 4. The list kit, shared by the two deck studios

Lists need the same behaviour in Presentation Studio (Decks, Published) and Training Studio
(Trainings, Published). It goes in one file both pages load,
`core/studio_core/deck_web/lists.js`, served by `core/studio_core/server.py` beside
`deck-panels.js` (`DECK_PAGES`). Plain DOM, no build step, no markup strings.

`window.StudioLists`:

- `filterRow({key, search, choices, more, open, set, changed, toggled})` returns a
  `form.filter-bar` with: a search field (`label.field.search`, widest, first), one
  `label.field` with a `select.input` per choice (equal share), a `details.more-filters`
  holding `more` when there are any, a plain `Search` submit button, and on a phone a
  `Filters` button (`.filters-toggle`) that says how many of the hidden filters are set
  ("Filters (2)"). Choices call `changed(name, value)` on change; the search applies on
  Search or Enter.
- `selectPage({id, label, shown, ticked, flip})` returns `label.check.select-page`, checked
  when every shown item is ticked and indeterminate when some are.
- `tick({id, label, on, flip})` returns `label.check` with its checkbox, 44px tall.
- `selectionBar({count, hidden, shown, unticked, actions, selectShown, clear})` returns
  `section.selection-bar.glass` (or `null` with nothing ticked): "N selected"; "N of them are
  not in this view." when ticked items are filtered out; "Select all N on this page" while
  some shown items are unticked; Clear; then the actions. Ticks stay through filter changes,
  and the bar says so the first time a tick is hidden.

There is no paging on these lists today; every item is on the page, so "Select all N
matching" is the same as "Select all N on this page" and is not offered. Blog Studio keeps
its own markup for the Team library.

### 5. One rule for every deck studio toolbar

`toolbar(spec)` in each deck studio's `app.js` orders `spec.actions`: the filled one first,
then the rest, each given `button-quiet`. A screen passes at most one filled action. A
screen-specific action with a long name goes in the page header's `.bar` (`spec.beside`)
instead. `foldActions` is removed: on a phone the toolbar actions wrap under the title, as
`.toolbar` already does (`flex-wrap: wrap`). While a selection bar is shown, its actions are
the screen's, and the toolbar's filled action stays as it is.

Each screen opens with `pageHead(lede, beside)`: `div.page-head` holding one `p.lede` and an
optional `.bar`. A screen has exactly one `.lede`.

A card has one heading: its `.card-title`. Row titles inside a card become `p.row-title`. A
panel that was an `h3`/`h4` section inside a card becomes a sibling card.

### 6. Presentation Studio, screen by screen

**Home.** Lede: "What needs you comes first, then decks in progress, then ways to start
one." The greeting stays above it. Toolbar: the filled "Review <title>" when something needs
you, then "New deck" (quiet); with nothing waiting, "New deck" is filled. Order: Needs you,
In progress, Run by your teammates, Start a deck (a new card: the three routes as buttons that
open the new-deck sheet at step 2 with that route chosen), Updates, Finished, then the foot.

**Decks.** Lede: "Every deck in this workspace, to find, open or delete." Toolbar: New deck
(filled), Bring in a deck, Published. A filter row: Search ("By its title, how it began,
where it stands or who runs it."), Where it stands (Any, Needs you, In progress, Finished,
Run by your teammates), How it began (Any, From an idea, From a document, From a deck you
have), Search. Under it a `.panel-heading` with the count ("3 of 7 decks match.") and
"Select all on this page". Each deck card that `deletable()` allows carries a tick. The
selection bar's action is "Delete N decks" (`button-danger`).

Delete N decks opens a sheet titled "Delete N decks?". It asks the runner what each would
lose, one deck at a time, with the existing `GET /api/delete?path=…`, and lists each deck as
"<title>: its folder and what only this computer kept for it." or, where the runner refuses,
"<title>: <the runner's reason> It stays." Then `DELETE_UNDO`, and "Delete N decks"
(danger) with Cancel. Sending deletes each deck with the existing `POST /api/delete
{path, title}` in turn; a refusal does not stop the rest. The toast says "Deleted N of M
decks." and names each one that stayed with the runner's words. No route changes.

**Published.** Lede: "N decks are published in this workspace, each at its latest
revision." The second sentence, "A revision is never moved once it is published.", becomes a
quiet line under the table. A filter row: Search, Delivered (Any, Delivered, Not delivered
yet), and under More filters, Published by (Anyone and each name in the list). The list is a
quiet `.table` with Deck, Revision, Published (when and by whom), Delivered, and one Open
per row; on a phone each row is a card (ui-kit's `.table` already does this). Nothing acts
on several published decks, so there is no selection here.

**New deck** becomes a sheet, `newSheet()`, opened by every "New deck" and by the Start a
deck card. `show('new')` and `?screen=new` still work: they open Home with the sheet open.
The sheet runs in numbered `.create-step`s, each with an `h3.sheet-part`:

1. How it begins (the three route cards).
2. For a document, "Your document"; for a deck, "Your deck and what changes". A deck from an
   idea has no step 2, so the numbers that follow close up.
3. What it is about.
4. How it looks (the brand and variant, then the closed Options disclosure).
5. Where it stops.

Then the "What happens when you start" sentences as one quiet paragraph, the problem line,
and a `.create-foot` with "Start the deck" (filled, the form's submit) and Cancel together.
The step builders return their nodes without a `.card` around them. Start checks every step
(`stepReady(draft, name)` for each name) and focuses the first missing answer. Cancel closes
the sheet and keeps the draft for the session, as leaving the wizard does now. "Back a step"
and "Another way to begin" go: every step is on the sheet, and the route is step 1.

**Bring in a deck** becomes: "1. Choose the deck" as pick cards, one per remembered deck,
then "Bring it in" (filled) and Cancel together.

**Research from** in the sheet uses the shared `fieldset.research-choices` with a
`label.check` tick for your documents (document route only), your sites (N) and the public
web, and the chosen sites as ticks in `.site-choices`. What is sent is unchanged.

**The deck screen** is kept light, because piece 5 replaces it for new decks:

- The intro's `.lede` (`run.sentence`) comes first, then the now-line and the state.
- "Undo the last step" moves into the page header's `.bar`.
- Ask for changes, Pause and Resume, when not the lead, are quiet (the toolbar rule).
- Order: notices, the problem, the worker's question, the gate line and the gate; then the
  note box, Slides taking shape and workers; then Where it is; then Delivered and Publish;
  then cost, every step, saved details, troubleshooting, Who runs this deck, Delete.
- "Review the direction" stops nesting: the research and the look become sibling cards
  after it. The research request becomes a form with its label "What should change in the
  research?", "Research again" and Cancel. Panel sub-headings become sibling cards; a
  question's `h4` becomes a `p.row-title`.
- On a phone the item-by-item stop's send moves from the toolbar into the review bar, filled,
  above the tab bar; on a desktop it stays in the toolbar.
- The outline row's picture form gains Cancel beside "Add the picture".

**Status.** Lede: "What is running, who runs it, and whether this computer has what a deck
needs." The "This computer" card comes first, so "Check this computer" shows its result where
the person is looking. Its items' titles become `p.row-title`.

**Settings.** Lede: "How Presentation Studio works on this computer; what every studio
shares is changed in Shared settings." Order: Shared settings, Where new work stops,
Workspace, Brand skill, Updates, Notifications, Your other studios, This page. "What a new
deck starts with" goes: its three facts (your name, brand, delivered as) join the Shared
settings card above "Change shared settings", because they are shared values. Studio-only
values stay one way away, through Workspace's "Change the set-up". "Turn on notifications"
is plain.

**Set-up.** Lede: "Say where your team keeps its decks and what a new deck starts with."
The rest of today's three sentences becomes a quiet line. Nothing else changes: its shared
fields stay, because first-run set-up needs them (see "Decisions for the owner").

**Spacing.** `deck.css`: `.pair` gap 0.6rem; `.slide-about` margin-top 0.6rem;
`.review-counts` margin `0.6rem 0`; `.outline-slide > details > * + *` 0.6rem. Lines inside
one row (0.35rem) stay.

### 7. Training Studio, screen by screen

**Home.** Lede: "What needs you comes first, then trainings in progress, then ways to start
one." Toolbar order by the rule. Order: Needs you, In progress, Run by your teammates, Start
a training (with the runner: a card with New training; without it, the sentence the
invitation gives), Updates, Your other studios, Finished, Cannot be read, then the foot.

**Trainings.** The lede stays: "N trainings on this computer, the one that changed last
first." Toolbar: New training (filled), Published. A filter row: Search (title, what it
says, who runs it), Where it stands (Any, Needs you, In progress, Finished, Run by your
teammates, Cannot be read), Search. "Select all on this page" on the `.panel-heading`; a tick
on each card the page may delete; the selection bar's "Delete N trainings" works as Decks'
does, through the existing `GET` and `POST /api/delete`. Card titles become `h2.card-title`.

**Published.** As Presentation Studio's: a filter row (Search, Delivered; Published by under
More filters) and a quiet table with one Open per row.

**New training** becomes a sheet with numbered steps:

1. Learning goal.
2. Materials.
3. Research (Research from as shared ticks, your sites, Add a site, research questions).
4. Where it stops, and the assistant and limits.

Then the "Ready to start" summary as a quiet paragraph, and "Start the training" (filled,
the submit) with Cancel together. The hidden submit and the toolbar's Continue go;
"Back a step" goes. `show('new')` opens Home with the sheet open.

**A picture a deck waits for** is asked in a sheet, "Add a picture", opened by "Add the
picture" in the deck card and by a `Needs you` line at the top of the run screen: "1. The
picture", "2. What it shows", "3. Where it came from, and any limit on its use", then "Add
the picture" (filled) and Cancel.

**The combined review**, kept light (piece 6 replaces it for new work):

- The primary follows the work. With nothing marked, "Approve the first drafts" (or "the
  finished materials") is filled. With anything marked "Needs changes", "Send N requests" is
  the filled one and Approve is quiet beside it.
- On a desktop both are in the toolbar and the bar holds the tally. On a phone the filled one
  moves into the bar, which sticks above the tab bar; the toolbar keeps the quiet one.
- "Looks good" is offered at every width.
- The card's own `.lede` becomes a quiet line; the screen keeps the run's lede.

**The run screen**, kept light: the `.lede` first in `runIntro`, then the now-line and beads.
Order: a worker's question, a problem, a Google copy conflict, a picture the deck waits for,
then the combined review or the gate, then work in progress, then finished. "Use this look"
is filled only when it is the lead. Pause, Resume, "Review X" when not the lead, and "Open the
index" are quiet.

**Gates**, kept light: each gate gets the lede "Read <label>, then approve it or ask for
changes."; the scenario-ownership and pictures sentences that were its `.lede` become quiet
lines. Ask for changes is quiet. A gate a combined review covers puts "Request changes in the
<review>" in the toolbar, filled.

**Training detail.** In the way, then Files; In the way, Left out or limited and Warnings are
drawn only when they hold something. Row titles in cards become `p.row-title`.

**Status, Settings, Index.** Status's lede: "What is running, who runs it, and whether this
computer has what a training needs."; This computer first. Settings' lede: "How Training
Studio works on this computer; what every studio shares is changed in Shared settings.";
order: Shared settings, Where new work stops, Workspace, Where each training is decided,
Brand skill, Updates, Notifications, Preview files in your Google Drive, This page; "Turn on
notifications" plain; "See the versions" only in Updates. The index's lede: "Everything this
training made, with where each file is."; "Download the index" becomes its toolbar primary.
Set-up: "Checked for you" becomes a `fieldset` with a `legend` in place of its `h3`.

### 8. Marketing Studio home and shared setup

**Home.** Lede: "Open a studio to start or continue your work." The large title stays. A
launch card that offers Connect makes Connect its filled button and "Open <Studio>" plain,
with Connect before Open; other cards keep "Open <Studio>" filled. The card's tile is
`.studio-symbol` (ui-kit draws it in the card's studio colours; `home.css` keeps only its
size and grid place). The status line is `stateLine`: Running is `done`, Ready is `none`, Not
installed is `off`. Order: the studio cards, then "Ready when you are", then "Continue on
your phone", then the note about the terminal.

**Shared settings.** One Save, at the end. Each `.setup-part` becomes its own card with an
`h3.card-title`: You and your assistant, Models for your work, Review level (step 1 in
first-run setup), Where your work lives (step 2), Brand, Delivery and previews (step 3),
Research sites (settings only). Model profiles are `fieldset.paper.profile-card` with a
`legend.field-label` ("Quick", "Main", "Complex") in place of `h5.sheet-part`.

**First-run setup.** The toolbar title is "Welcome to <product>"; the workflow steps show the
three steps; the card titles are the only headings. `#step-label` and the large
`#settings-title` are hidden while setting up. The step labels match the first card of each
step: "You and your assistant", "Where your work lives", "Brand and delivery". Lede: "Set up
once, and every studio starts with these choices." The announcement for screen readers ("Step
1 of 3: …") stays.

**This computer.** Lede: "Check the tools your studios need on this computer." The second
sentence, "Each studio checks sign-in when you use it.", becomes a hint under the results.
"Check computer" moves into the toolbar (filled) on this screen only. Item titles become
`p.row-title`. "Studio installations" stays in Shared settings, saved by Save settings: the
owner decided on 2026-10-27 to keep one save rather than move the card here with its own.

**Research sites** become a `.table` with one Remove per row (`tr.site-row`, the site in its
first cell, Remove in its last); `home.css` keeps only `.site-row > td:first-child`'s
wrapping.

**Spacing.** `.studio-list` gap 1.1rem; the 0.8rem group gaps become 0.6rem.

### 9. Moved controls

Every function stays reachable. The page journeys in each studio's `test_layout.py`, and the
root `tests/test_layout_pass.py`, reach each control in its new place.

**Presentation Studio**

| Control | Was | Now |
| --- | --- | --- |
| New deck (the form) | A full-page wizard, two or three pages after the route cards | One sheet, numbered steps, opened by New deck on Home and Decks and by Start a deck on Home |
| Back a step, Another way to begin | The wizard's foot | Gone: every step is on the sheet; Cancel closes it |
| Continue | The wizard's foot | Gone: Start the deck ends the sheet |
| Find a deck | A search box applied as typed | Search in the Decks filter row, with Where it stands and How it began |
| Delete (several decks) | One deck at a time | Tick the decks, then Delete N decks in the selection bar; Delete on each card stays |
| What a new deck starts with → Change them | A Settings card | Its facts in the Shared settings card; studio-only values through Workspace → Change the set-up |
| Undo the last step | The deck toolbar | The deck's page header, beside the lede |
| Toolbar actions on a phone | A More menu | Wrapped under the title |
| The item-by-item send on a phone | The toolbar | The review bar, above the tab bar |
| This computer (result) | Last on Status | First on Status |
| Research from | Chips | Ticks in a Research from group |
| Request changes to the research (direction review) | A disclosure under the look | Its own card after Review the direction, with Cancel |
| Bring in "<deck>" | A button per deck | A pick card per deck, then Bring it in |
| Updates | Above Needs you on Home | After Start a deck |
| Published decks | Rows in a card | A table, one Open per row |

**Training Studio**

| Control | Was | Now |
| --- | --- | --- |
| New training (the form) | Three pages, Continue or Start in the toolbar | One sheet, numbered steps, Start the training and Cancel at its end |
| Back a step | The form's foot | Gone |
| Send N requests | A plain button in the review bar | The filled toolbar action once something is marked (the bar's on a phone) |
| Approve the first drafts / the finished materials | Always filled | Filled while nothing is marked; quiet beside Send N requests otherwise |
| Looks good | Phone only | Every width |
| Supply the picture, What it shows, Where it came from, Any limit | A form in a row of the deck card | The Add a picture sheet, from the deck card and from the top of the run screen |
| Use the Doc's version, Keep this version and send it | In Copies, after Workers and Steps | Near the top of the run screen, with what needs you |
| Request changes in the <review> | A plain button in a callout | The gate's toolbar, filled |
| Download the index | A quiet button under the document | The index's toolbar, filled |
| Toolbar actions on a phone | A More menu | Wrapped under the title |
| Turn on notifications | Filled | Plain |
| See the versions | Updates and Brand skill cards | Updates only |
| Delete (several trainings) | One at a time | Tick, then Delete N trainings in the selection bar |
| This computer (result) | Last on Status | First on Status |
| Updates, Your other studios | Above Needs you on Home | After Start a training |
| Research from | Chips | Ticks in a Research from group |

**Marketing Studio**

| Control | Was | Now |
| --- | --- | --- |
| Check computer | A filled button under the Tools list | This computer's toolbar |
| Studio installations | Shared settings, with its own Save installation folders | Shared settings, saved by Save settings (owner, 2026-10-27) |
| Review level | Inside You and your assistant | Its own card, step 1 of first-run setup |
| Models for your work | Inside You and your assistant | Its own card |
| Delivery and previews | Inside Brand and delivery | Its own card, step 3 |
| Connect | A plain button under the status | The card's filled button, before Open |
| Step 1 of 3, the large step title | Above the steps in setup | Gone: the workflow steps and the card title say it |

**Blog Studio:** nothing moves. Classes are renamed (`library-selection` → `selection-bar`,
`stack`, `page-head`); ids and routes stay.

## Decisions for the owner

1. **No re-sync needed.** Every studio's `style.css` and `markdown.js` is a symlink to
   `ui-kit/`. A root test now checks they stay links. The stale pin
   `training-studio-ui.json` is deleted.
2. **Published has filters but no selection.** No action takes several published decks or
   trainings. A selection bar with nothing to do is left out.
3. **No "Select all N matching".** Deck and training lists are not paged; everything
   matching is on the page.
4. **Bulk delete is page-only.** It calls the existing per-item delete route once per item,
   so no route, record or state changes, and Training Studio's matrix needs no row.
5. **Delete in a selection bar is a danger button, not filled,** so each screen keeps one
   filled button while ticking.
6. **The new-deck and new-training forms become sheets now,** as asked. Pieces 5 and 6
   design desk starts; if they replace these sheets, the sheets' step builders are what they
   reuse.
7. **Set-up keeps its shared fields.** Presentation Studio's and Training Studio's first-run
   set-up still need them. Sending first run through Marketing Studio's "Welcome to
   <Studio>" page, as Blog Studio does, is a workflow change for piece 1 or 7, not layout.
8. **Blog Studio differs in two places:** its Home rows are `h3.row-title` inside a card,
   and its Home toolbar puts New blog before Review. This piece leaves Blog Studio as it is;
   bringing it in line is a two-line change if the owner wants it.
9. **Row titles are no longer headings** in the deck studios (one heading per card). A screen
   reader still reaches each row through its list and its named button.

## Not here

- Copy fixes, including the words of ledes another piece rewrites: piece 1. The ledes here
  are the one sentence the rule needs.
- Dead CSS (`deck.css:25-32` `.bead-later`, Blog's unused classes), stale README lines and
  the shared runner: piece 2.
- The desk parts and `.desk-*` styles: piece 3.
- The deck desk and the training desk, including their starts: pieces 5 and 6. Their
  screens get the light version above.
- Paging the deck and training lists; any new route.

## Testing

- **Root.** `tests/test_ui_consistency.py`: the moved components are in the kit and in no
  page stylesheet; every shared control is at least 2.75rem; the review bar and the selection
  bar sit at `var(--tab-bar-room)` on a phone; `deck-panels.css` passes the page-stylesheet
  guard; every studio's `style.css` and `markdown.js` is a link into `ui-kit/`; `home.css`
  draws no tile, no dot and no ruled list. `tests/test_layout_pass.py`: Marketing Studio's
  pages, statically and through `settings_page_harness.js`.
- **Blog Studio.** `check-management.cjs` and the suite pass unchanged; one check confirms
  the bar's class is `selection-bar` and its id is still `library-selection`.
- **Presentation Studio and Training Studio.** The page harnesses gain a `tick` step and
  snapshot fields for the toolbar, the ledes, card headings and part order. `run_page` checks
  on every snapshot: at most one filled, the filled one first in the toolbar, the rest quiet,
  at most one lede, one heading level per card. New `test_layout.py` files walk each screen
  at desktop and phone width and reach every moved control.
- Tests use disposable data folders and scripted answers. No provider, Google or assistant
  job runs.
