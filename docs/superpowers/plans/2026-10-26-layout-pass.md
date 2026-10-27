# Piece 4, the layout pass: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Presentation Studio, Training Studio and Marketing Studio's home and shared setup
follow the Layout rules in `docs/design/golden-gate.md`: one filled primary first in each
toolbar, one lede, content in the order a person works, filter rows and a selection bar on
lists, numbered sheets for what makes something, one heading per card, 44px controls and no
bar under the phone tab bar. The components those rules name move out of Blog Studio's
`blog.css` into `ui-kit/style.css` first, with Blog Studio unchanged.

**Architecture:** CSS moves into `ui-kit/style.css` (every studio links it). One new shared
page script, `core/studio_core/deck_web/lists.js` (`window.StudioLists`), served beside
`deck-panels.js` by `core/studio_core/server.py`, gives both deck studios the filter row,
ticks and the selection bar. Each deck studio's `toolbar(spec)` orders actions centrally and
`foldActions` goes. Screens change in each studio's own `desk/app.js`. Marketing Studio's
changes are in `core/studio_core/setup_web/{index.html,app.js,home.css}`. No route, record or
state changes.

**Tech Stack:** Python 3.11 standard library; plain JavaScript with no build step;
`unittest`; the studios' `page_harness.js` journeys; Blog Studio's `check-management.cjs`;
the root `tests/settings_page_harness.js`.

**Spec:** `docs/superpowers/specs/2026-10-26-layout-pass-design.md`. Read it with this plan.
Context: `docs/superpowers/specs/2026-10-26-workflow-audit.md` and section 4 of
`2026-10-26-workflow-audit/presentation.md` and `training.md`, Part B.1 and C.7 of
`blog-and-shared.md`.

**Before starting:** pieces 1, 2 and 3 have merged. Re-read every file and line named here
on the current `main`. Piece 1 changed words: find each control by what it does, not by its
label, and keep piece 1's words where it rewrote a sentence quoted here. Piece 3 moved the
`.desk-*` rules; if it also moved any rule this plan moves, skip that rule.

## Global Constraints

- Pieces are built in order (1 to 6), each merged before the next starts. Line references are at
  main cc53056: re-read every named file on the piece's own base first. Training matrix row
  numbers named here are a guide; each new row takes the next free number on that base.
- Python 3.11 or newer, standard library only; no frontend build step; no markup strings in
  page scripts (the harnesses have no HTML parser and fail on `innerHTML`).
- UI follows `docs/design/golden-gate.md`: glass only for the sidebar, toolbar, sheets,
  selection bars and toasts; forms, lists and documents opaque. A page stylesheet sizes and
  places; it never draws a shared control and takes every colour from a token.
- Full product names in code, docs and commits: Marketing Studio, Blog Studio, Presentation
  Studio, Training Studio, Harness Slides, Harness Research.
- Person-facing sentences never say "artifact", "stale" or "lineage". Presentation Studio
  names no brand (`tests/test_no_brand_named.py`).
- No route, record format, status, approval or readiness changes. Bulk delete calls the
  existing `GET /api/delete?path=` and `POST /api/delete {path, title}` once per item, so
  Training Studio's state-transition matrix needs no row.
- Saved work keeps working: a deck or training started before this piece opens on the same
  screens, with the new layout.
- No guidance changes, so no `minimum_runtime` or `VERSION` change. If a guidance file is
  found that names a moved control, change its words only, and run that studio's
  `validate_package.py`.
- Presentation Studio: a file ported from Training Studio stays listed in `vendor.json`;
  append "layout pass, piece 4" to the `note` of `desk/app.js` and `tests/page_harness.js`.
- Tests use disposable data folders (`PRESENTATION_STUDIO_DATA`, `HOME`, `STUDIOS_CONFIG`),
  scripted answers and the harnesses. No provider, Google or assistant job.
- Commit messages are plain sentences; end each with the attribution line the session gives.

## Review Focus

1. Blog Studio looks the same: every moved rule keeps Blog's declarations (Task 1's
   `test_moved_rules_keep_blog_studios_values`), and `check-management.cjs` passes untouched.
2. The new-deck and new-training sheets send exactly the body the wizards sent (Tasks 7 and
   11 compare with the bodies today's tests assert).
3. Bulk delete sends nothing before its confirm, and one refusal does not stop the rest
   (Tasks 6 and 10).
4. On a phone nothing sits under the tab bar and every toolbar action is reachable without a
   More menu (Tasks 2, 4, 8 and 12).
5. Every row of the spec's "Moved controls" tables has a journey that reaches the control in
   its new place (Tasks 5 to 13).

---

## Task 1: The shared components move into ui-kit; Blog Studio switches with nothing changed

**Files:**
- Modify: `ui-kit/style.css` (a new section "lists, sheet steps and page heads", after
  `.table`), `studios/blog/skills/blog-studio/assets/management/blog.css`,
  `studios/blog/skills/blog-studio/assets/management/index.html`,
  `docs/design/golden-gate.md` (the component table)
- Delete: `studios/blog/skills/blog-studio/assets/management/training-studio-ui.json` and
  its sentence in `studios/blog/skills/blog-studio/references/package-notes.md:26` (skip if
  piece 2 deleted them)
- Test: `tests/test_ui_consistency.py`

**Interfaces (Produces):** ui-kit classes `.filter-bar`, `.filter-bar .search`,
`.more-filters`, `.filters-toggle`, `.filters-open`, `.panel-heading`, `.select-page`,
`.selection-bar`, `.selection-count`, `.selection-actions`, `.create-flow`, `.create-step`,
`.create-foot`, `.sheet-heading`, `.stack`, `.page-head`, `.research-choices`,
`.site-choices`, `.check`, and `.card[data-studio] > .studio-symbol`.

- [ ] **Step 1: Write the failing tests** in `tests/test_ui_consistency.py`.
  - Add to `COMPONENTS`: `'.filter-bar', '.more-filters', '.filters-toggle',
    '.panel-heading', '.select-page', '.selection-bar', '.selection-count',
    '.selection-actions', '.create-flow', '.create-step', '.create-foot', '.sheet-heading',
    '.stack', '.page-head', '.research-choices', '.site-choices', '.check'`. The existing
    `test_kit_defines_every_shared_component` then fails.
  - Add the same names, without dots, to `SHARED`, so `test_page_stylesheets_only_lay_out`
    refuses a page stylesheet that draws them.
  - `test_moved_components_are_defined_only_in_the_kit`: for each of `blog.css`, `home.css`,
    `deck.css`, no rule's last compound styles `filter-bar`, `more-filters`,
    `filters-toggle`, `library-selection`, `selection-bar`, `create-flow`, `create-step`,
    `create-foot`, `sheet-heading`, `research-choices`, `site-choices` or `check` with any
    non-layout property, and no selector names `library-selection` or `#studio-page>`.
  - `test_moved_rules_keep_blog_studios_values`: a literal dict, copied from `blog.css` at
    the base commit, of selector → declarations for the rules in the spec's table (for
    example `'.filter-bar .search': 'flex:2 1 14rem;min-width:12rem'`,
    `'.create-step': 'padding-top:.9rem;border-top:1px solid var(--hair)'`,
    `'.sheet-heading': 'position:sticky;top:0;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:1rem;background:var(--sheet-fill);border-bottom:1px solid var(--hair);padding-bottom:.75rem'`).
    Normalise whitespace and leading zeros, rename `library-selection` to `selection-bar`,
    and assert each appears in `ui-kit/style.css` with the same declarations.
  - `test_blog_studios_bar_keeps_its_id`: Blog's `index.html` has an element with
    `id="library-selection"` whose class list is `selection-bar glass`, and
    `id="studio-page"` with class `stack`.
- [ ] **Step 2: Run to fail:** `PYTHONPATH=.:tests python3 -m unittest tests.test_ui_consistency -v`.
- [ ] **Step 3: Move the rules.** Copy each into `ui-kit/style.css` in the kit's own
  formatting (one declaration a line), renaming `.library-selection` to `.selection-bar`
  and `#studio-page>*+*` to `.stack > * + *`; `#editorial-screen>.view-head` and its `.lede`
  rule become `.page-head` and `.page-head > .lede`. The phone rules go into the existing
  `@media (max-width: 52rem)` block. The room rule becomes
  `.content:has(.selection-bar:not([hidden])) { padding-bottom: calc(12rem + env(safe-area-inset-bottom)); }`
  in that block. Add `.card[data-studio] > .studio-symbol { background: var(--studio-wash);
  color: var(--studio-color); box-shadow: none; }`. Delete the moved rules from `blog.css`;
  rewrite Blog-only rules that name them (`.library-selection .bar` → `.selection-bar .bar`).
- [ ] **Step 4: Switch Blog's markup.** In `index.html`: `library-selection glass` →
  `selection-bar glass`; `<div id="studio-page">` → `<div id="studio-page" class="stack">`;
  `class="view-head"` → `class="page-head view-head"`. No change to `app.js`, `runner.js` or
  `desk.js` is needed: they use ids and the unchanged class names.
- [ ] **Step 5: Docs.** `docs/design/golden-gate.md`'s component table gains rows: Filters
  (`.filter-bar`, `.more-filters`, `.filters-toggle`), Selection (`.panel-heading`,
  `.select-page`, `.selection-bar`), Sheet steps (`.create-flow`, `.create-step`,
  `.create-foot`, `.sheet-heading`), Page (`.stack`, `.page-head`), Ticks (`label.check`,
  `.research-choices`, `.site-choices`). Change "Blog Studio follows them; apply the same
  rules to …" to "Every studio follows them."
- [ ] **Step 6: Run to pass:** the root command above, then
  `node studios/blog/scripts/ci/check-management.cjs` and
  `python3 studios/blog/scripts/ci/run_tests.py test_editorial_tools test_team_library test_blog_runner`.
- [ ] **Step 7: Commit:** "Move the filter row, selection bar, sheet steps and research choice into the shared stylesheet".

## Task 2: Every control is 44px, and no bar sits under the phone tab bar

**Files:**
- Modify: `ui-kit/style.css` (`.seg-option` :675, `.menu-item` :715, `.input` :1279, `.chip`
  :1341, the phone block :2199, `.review-bar` :2760),
  `core/studio_core/deck_web/deck-panels.css` (drop literal fallbacks),
  `studios/presentation/skills/presentation-studio/scripts/desk/deck.css` (`.review-bar`
  keeps only margin and padding)
- Test: `tests/test_ui_consistency.py`

**Interfaces (Produces):** the custom property `--tab-bar-room`, defined in the phone block.

- [ ] **Step 1: Write the failing tests** in `tests/test_ui_consistency.py`.
  - Add `ROOT / 'core/studio_core/deck_web/deck-panels.css'` to `PAGE_STYLES`.
  - `test_every_shared_control_is_at_least_44px`: in the kit's top-level rules,
    `min-height` of `.button`, `.nav-item`, `.seg-option`, `.chip`, `.menu-item`, `.input`,
    `.select-page`, `.more-filters > summary` is at least `2.75rem` or `44px`; inside the
    `@media (max-width: 52rem)` block, `.link` and `.input[type="file"]::file-selector-button`
    have `min-height: 2.75rem`. A helper `rem(value)` reads `2.75rem` as 2.75 and `44px` as
    2.75.
  - `test_bars_sit_above_the_tab_bar_on_a_phone`: the phone block defines `--tab-bar-room`;
    its `.review-bar` rule has `bottom: var(--tab-bar-room)` and `z-index: 4`; its
    `.selection-bar` rule has `position: fixed` and `bottom: var(--tab-bar-room)`; the
    `.sidebar` rule's `z-index` (6) is larger than both.
  - `test_studio_pages_link_the_kit`: for every `style.css` and `markdown.js` under
    `studios/*/skills/*/scripts/desk/`, `studios/blog/skills/blog-studio/assets/management/`,
    `core/studio_core/setup_web/` and `marketing_studio/web/`, `path.is_symlink()` and
    `path.resolve() == ROOT / 'ui-kit' / path.name`.
- [ ] **Step 2: Run to fail:** `PYTHONPATH=.:tests python3 -m unittest tests.test_ui_consistency -v`.
- [ ] **Step 3: Implement.** Raise the four `min-height`s to `2.75rem`. In the phone block
  add `:root { --tab-bar-room: calc(4.4rem + env(safe-area-inset-bottom)); }`, `.link {
  display: inline-flex; align-items: center; min-height: 2.75rem; }`, the file button's
  `min-height: 2.75rem`, `.review-bar { bottom: var(--tab-bar-room); z-index: 4; }`, and the
  selection bar's `bottom: var(--tab-bar-room)` in place of Blog's
  `calc(4.4rem + env(safe-area-inset-bottom))`. Repeat the `.link` and file-button rules in
  `@media (pointer: coarse)`. In `deck-panels.css` replace `var(--paper, #fff)` and the other
  fallbacks with the bare tokens.
- [ ] **Step 4: Run to pass:** the root command, then `node studios/blog/scripts/ci/check-management.cjs`.
- [ ] **Step 5: Commit:** "Make every shared control 44px and keep the review and selection bars above the phone tab bar".

## Task 3: The list kit and the harnesses that see layout

**Files:**
- Create: `core/studio_core/deck_web/lists.js`
- Modify: `core/studio_core/server.py` (`DECK_PAGES`, about :472),
  `studios/presentation/skills/presentation-studio/scripts/desk/index.html`,
  `studios/training/skills/training-studio/scripts/desk/index.html` (load `lists.js` after
  `deck-panels.js`), `studios/presentation/tests/page_harness.js`,
  `studios/training/tests/page_harness.js`
- Test: `studios/presentation/tests/test_desk.py` (`test_the_page_and_its_stylesheets_are_served_and_nothing_else`),
  `studios/presentation/tests/test_page_app.py:102`, `studios/training/tests/test_desk.py:1504`,
  and a new `studios/presentation/tests/test_lists_kit.py`

**Interfaces (Produces):** `window.StudioLists` with

- `filterRow({key, search: {id, label, hint, value}, choices: [{id, label, options:
  [[value, text]], value}], more: [same], open, changed(name, value), searched(text),
  toggled()}) -> HTMLFormElement` (`form.filter-bar`; the toggle is
  `button.button.filters-toggle` named "Filters" or "Filters (N)")
- `selectPage({id, label, shown: [id], ticked: Set, flip(on)}) -> HTMLLabelElement`
- `tick({id, label, on, flip(on)}) -> HTMLLabelElement` (`label.check`)
- `selectionBar({ticked: Set, shown: [id], noun: ['deck', 'decks'], actions: [{label, kind,
  run, key}], selectShown(), clear()}) -> HTMLElement | null`

Harness additions, the same in both studios:

- a step `{tick: the name of a check box}`: the visible `INPUT` with `type === 'checkbox'`
  whose label (an ancestor `LABEL`, or `label[for]`) reads that name; flips `checked`,
  clears `indeterminate`, fires `change`.
- snapshot fields: `toolbar` (each visible control inside `#actions`, as `{name, filled,
  quiet}`), `ledes` (the text of each visible `.lede` inside `#main` and `#sheet`),
  `cardHeadings` (for each visible `.card` in `#main`, the sorted distinct heading tags inside
  it but outside any nested `.card`), `nested` (how many visible `.card`s sit inside another
  `.card`), `parts` (the text of each visible `.card-title`, `.sheet-part` and
  `.selection-count` in document order), `ticked` (names of checked boxes), `bar` (the words
  of a visible `.selection-bar`, or '').
- `FakeNode` keeps `checked` and `indeterminate` on inputs, and `name()` of an input is its
  label's words.
- `ScriptedPage.run_page(answers, steps, layout=False, **plan)` in both `test_desk.py`
  files: with `layout=True` it also checks every snapshot: `len(shot['ledes']) <= 1`, every
  entry of `shot['cardHeadings']` has at most one tag, `shot['nested'] == 0`, and, when
  `shot['toolbar']` has a filled control, it is the first and the others are quiet. Every
  `test_layout.py` journey passes `layout=True`. Task 12 makes it the default.

- [ ] **Step 1: Write the failing tests.**
  - The served-file tests in both studios expect `'/lists.js'` beside `'/deck-panels.js'`;
    the index test at `test_page_app.py:102` and `training/tests/test_desk.py:1504` expects
    `lists.js` loaded after `deck-panels.js`.
  - `studios/presentation/tests/test_lists_kit.py`, `ListsKitTests`, runs the harness with a
    plan `{kit: true, steps}` that builds the kit's parts on an empty page (a new harness mode
    `node page_harness.js kit FILE`):
    - `test_the_filter_row_puts_search_first_and_counts_hidden_filters`: a row with search
      and two choices, one set, at phone width: the controls in order are the search box, the
      two selects, `Search`; the toggle reads `Filters (1)`; on a desktop no toggle is shown.
    - `test_a_choice_applies_on_change_and_search_on_submit`: choosing an option calls
      `changed('stands', 'needs')` once; typing does nothing until `Search` is pressed, then
      `searched('capacity')`.
    - `test_the_bar_counts_what_is_out_of_view_and_offers_the_page`: ticked `{a, b, c}`,
      shown `[a, d]`: the bar reads `3 selected`, `2 of them are not in this view.`, offers
      `Select all 2 on this page`, `Clear` and the action; with nothing ticked it is `null`.
    - `test_select_all_on_this_page_is_mixed_when_some_are_ticked`: shown `[a, b]`, ticked
      `{a}`: the box is unchecked and `indeterminate`; ticking it calls `flip(true)`.
- [ ] **Step 2: Run to fail:** `cd studios/presentation/tests && python3 -m unittest test_lists_kit test_desk.PageFileTests test_page_app -v`
  and `cd studios/training/tests && python3 -m unittest test_desk -k served -v`.
- [ ] **Step 3: Write `lists.js`** in the style of `deck-panels.js` (an IIFE, its own
  `make`). Words: "Search", "Filters", "Filters (N)", "More filters", "N selected", "1 of them
  is not in this view." / "N of them are not in this view.", "Select all N on this page",
  "Clear", "Select all on this page". Add it to `DECK_PAGES`; load it in both `index.html`
  files; load it in both harnesses after `deck-panels.js`.
- [ ] **Step 4: Add the harness fields and the opt-in `run_page` checks.** Existing journeys
  keep `layout=False` until Task 12.
- [ ] **Step 5: Run to pass:** the commands of Step 2.
- [ ] **Step 6: Commit:** "Add a shared list kit for filters, ticks and the selection bar, and let the page harnesses see layout".

## Task 4: One toolbar rule in both deck studios

**Files:**
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js`
  (`toolbar` :1040, `foldActions` :633 removed, its callers such as `paintDeck` :5737),
  `studios/training/skills/training-studio/scripts/desk/app.js` (`toolbar`, `foldActions`
  :755 removed, its callers)
- Test: `studios/presentation/tests/test_layout.py` (new), `studios/training/tests/test_layout.py` (new)

**Interfaces (Produces):** in each studio's `app.js`, `pageHead(lede, beside) ->
HTMLElement` (`div.page-head` with `p.lede` and, when given, `div.bar`); `toolbar(spec)`
orders `spec.actions` filled first and adds `button-quiet` to every other `.button`.

- [ ] **Step 1: Write the failing tests.** Each `test_layout.py` does `import test_desk`
  (never `from test_desk import` a test class, so no existing class runs twice) and holds
  `LayoutTests`:
  - Presentation: `LayoutTests(test_desk.ScriptedPage, test_runner_page.PageCase)`, with
    `answers = test_desk.ScreenTests.answers` and `deck_screen =
    test_desk.ScreenTests.deck_screen`.
  - Training: `LayoutTests(test_desk.ScriptedPage, test_desk.PageCase)`, with `answers =
    test_desk.RunnerScreenTests.answers`.
  - Both carry `@unittest.skipUnless(test_desk.NODE, …)` as the existing classes do.
  - `test_the_filled_action_comes_first_and_the_rest_are_quiet`: Home with a deck (or
    training) waiting: `shot['toolbar'][0] == {'name': 'Review <title>', 'filled': True,
    'quiet': False}` and every other entry has `quiet: True`.
  - `test_a_phone_wraps_the_toolbar_and_has_no_more_menu`: the deck (or run) screen of a
    paused run with `narrow: True`: `shot['toolbar']` names `Resume`, `Stop` and, in
    Presentation, nothing named `More`; `'More'` is not in `shot['buttons']`.
- [ ] **Step 2: Run to fail:** `cd studios/presentation/tests && python3 -m unittest test_layout -v`;
  `cd studios/training/tests && python3 -m unittest test_layout -v`.
- [ ] **Step 3: Implement** the ordering in `toolbar(spec)`, add `pageHead`, delete
  `foldActions` and pass actions straight through. Update the three existing journeys that
  click `More` (`grep -n "'click': 'More'" studios/*/tests/*.py`) to click the action itself.
- [ ] **Step 4: Run to pass:** both commands, plus `python3 -m unittest test_desk` in each
  studio's `tests/`.
- [ ] **Step 5: Commit:** "Put the filled action first in every deck studio toolbar and wrap the rest on a phone".

## Task 5: Presentation Studio Home, Status, Settings and Set-up

**Files:**
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js` (`drawHome`
  :1470, `deckRow` :1402, `drawStatus` :1687, `computerItem` :1598, `drawSettings` :1727,
  `defaultsCard` :1714 removed, `alertsCard` :1700, `paintSetup` :2540), `deck.css` (spacing)
- Test: `studios/presentation/tests/test_layout.py`

**Interfaces (Produces):** `startCard() -> HTMLElement` ("Start a deck"), whose route
buttons call `openNew(route)` (Task 7 makes `openNew` open the sheet; until then it calls
`show('new')` and sets `view.draft.route`).

- [ ] **Step 1: Write the failing tests** in `test_layout.py`:
  - `test_home_puts_what_needs_you_first_and_setup_after_ways_to_start`: decks needing you,
    working and finished: `shot['ledes'] == ['What needs you comes first, then decks in
    progress, then ways to start one.']`; `shot['parts']` begins `['Needs you', 'In
    progress']`, then `'Start a deck'`, then `'Updates'` when shown, then `'Finished'`.
  - `test_start_a_deck_opens_the_form_at_its_route`: clicking `From a document` in Start a
    deck shows the document step (`'Your document'` in `shot['parts']` or the heading).
  - `test_status_shows_the_check_first`: after `Check this computer`, the first entry of
    `shot['parts']` is `'This computer'`.
  - `test_settings_has_one_way_to_each_value`: `shot['ledes'] == ['How Presentation Studio
    works on this computer; what every studio shares is changed in Shared settings.']`;
    `'What a new deck starts with'` not in `shot['parts']`; the Shared settings card's words
    hold the person's name and the brand; `'Change shared settings'` and `'Change the
    set-up'` are in `shot['buttons']`; `'Change them'` is not; `shot['filled'] == []`.
  - `test_set_up_has_a_one_sentence_lede`: `shot['ledes'] == ['Say where your team keeps
    its decks and what a new deck starts with.']`.
  - Moved controls: `test_moved_controls_on_home_status_and_settings_are_reachable`: from
    Settings, `Change the set-up` opens Set-up; `Change shared settings` sets
    `location.href` to `/onboarding/#token=…` (the harness records it).
- [ ] **Step 2: Run to fail:** `cd studios/presentation/tests && python3 -m unittest test_layout -v`.
- [ ] **Step 3: Implement** the spec's section 6 for these screens: ledes through
  `pageHead`, the part order, `startCard`, row titles as `p.row-title`, the computer card
  first, Settings' order with `defaultsCard`'s facts in the Shared settings card,
  `Turn on notifications` plain, the set-up lede (the rest a `p.quiet`). `deck.css`: `.pair`
  gap `0.6rem`, `.slide-about` margin-top `0.6rem`, `.review-counts` margin `0.6rem 0`,
  `.outline-slide > details > * + *` `0.6rem`.
- [ ] **Step 4: Run to pass:** `python3 -m unittest test_layout test_desk -v`.
- [ ] **Step 5: Commit:** "Lay out Presentation Studio's Home, Status, Settings and Set-up in the order a person works".

## Task 6: Presentation Studio Decks and Published

**Files:**
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js` (`deckCard`
  :1497, `matching` :1513, `drawDecks` :1523, `publishedRow` :6918, `paintPublished` :6936;
  a new `bulkDeleteSheet()` beside `deleteSheet` :6131, and its case in `drawSheet` :1316)
- Test: `studios/presentation/tests/test_layout.py`; update the journey at
  `test_desk.py:1785` (`{'fill': 'Find a deck', …}`)

**Interfaces (Produces):** `view.filters.decks = {text, stands, began}`,
`view.filters.published = {text, delivered, by}`, `view.ticked.decks: Set` of deck paths.

- [ ] **Step 1: Write the failing tests** in `test_layout.py`:
  - `test_decks_filter_by_where_it_stands_and_how_it_began`: four decks (one needs you, one
    working from a document, two finished from an idea). Choosing `Finished` in `Where it
    stands` leaves two cards and `2 of 4 decks match.`; then `From a document` leaves none.
    Typing `capacity` in Search changes nothing until `Search` is pressed.
  - `test_a_phone_shows_search_and_a_filters_button`: `narrow: True`: `Where it stands` is
    not visible; `Filters` is; after choosing a filter and pressing `Filters` again it reads
    `Filters (1)`.
  - `test_ticks_survive_filter_changes_and_the_bar_says_so`: tick two finished decks, then
    filter to `Needs you`: `shot['bar']` holds `2 selected` and `2 of them are not in this
    view.`; `Clear` empties it and hides the bar.
  - `test_deleting_several_decks_asks_first_and_carries_on_past_a_refusal`: tick three
    decks; `Delete 3 decks` opens `Delete 3 decks?`; the requests so far are three
    `GET /api/delete?path=…` and no POST. The runner refuses the second
    (`{may: false, why: 'Someone else runs it.'}`): the sheet lists it with `Someone else runs
    it. It stays.` and the button reads `Delete 2 decks`. Pressing it posts exactly two
    `/api/delete` bodies `{path, title}`, and the toast reads `Deleted 2 of 2 decks.`
  - `test_a_failed_delete_is_named_and_the_others_go`: two ticked, the first POST answers
    `409 {error: 'It is working now.'}`: the second is still posted; the toast reads `Deleted
    1 of 2 decks. <title>: It is working now.`
  - `test_published_is_a_table_with_one_open_per_row`: two published entries: one `table`
    with two rows; each row's only button is `Open <title>`; `Delivered` choice `Not delivered
    yet` leaves one row; `Published by` sits under `More filters`; `shot['ledes'] == ['2 decks
    are published in this workspace, each at its latest revision.']`.
  - Moved controls: `test_find_a_deck_and_delete_are_reachable`: `Search` is in the Decks
    filter row; `Delete <title>` is still on each deletable card.
- [ ] **Step 2: Run to fail:** `python3 -m unittest test_layout -v`.
- [ ] **Step 3: Implement** with `StudioLists.filterRow`, `selectPage`, `tick` and
  `selectionBar`. A deck card's title becomes `h2.card-title`; its tick is offered only when
  `deletable(brief)`. `bulkDeleteSheet` reads each preview in turn with `ask('delete',
  {path})`, then `settleBulkDelete` sends `send('delete', {path, title})` in turn, collects
  refusals, clears the deleted ticks, toasts, and redraws. Published becomes a `.table` with
  `cell(...)` data-labels. Update the `Find a deck` journey to fill `Search` and press
  `Search`.
- [ ] **Step 4: Run to pass:** `python3 -m unittest test_layout test_desk -v`.
- [ ] **Step 5: Commit:** "Give Presentation Studio's Decks a filter row and a selection bar, and Published a table".

## Task 7: Presentation Studio's new-deck sheet, Bring in a deck, and the shared research choice

**Files:**
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js`
  (`routeStep` :2710, `aboutStep`, `documentStep`, `deckStep`, `startStep` :3158,
  `paintNew` :3191, `drawNew` :3222, `stepReady` :3232, `nextStep` :3275 removed,
  `newButton` :1377, `researchFromField` :3057, `bringSheet` :1558, `drawSheet` :1316,
  `draw` :1180)
- Test: `studios/presentation/tests/test_layout.py`; update the `Continue` journeys in
  `test_desk.py` (15 of them: `grep -n "'Continue'" studios/presentation/tests/test_desk.py`)

**Interfaces (Produces):** `openNew(route)`; `newSheet() -> [nodes]` (the `new` case of
`drawSheet`); each step builder returns `{title, nodes}`; `stepReady(draft, name) ->
bool`; `createStep(number, title, ...nodes) -> HTMLElement` (`section.create-step` with
`h3.sheet-part` "N. Title").

- [ ] **Step 1: Write the failing tests** in `test_layout.py`:
  - `test_new_deck_is_one_sheet_in_numbered_steps`: `New deck`, choose `From a document`:
    `shot['sheet']` holds `1. How it begins`, `2. Your document`, `3. What it is about`,
    `4. How it looks`, `5. Where it stops`; the last two buttons of the sheet are `Start the
    deck` (filled) and `Cancel`.
  - `test_an_idea_has_no_source_step_and_the_numbers_close_up`: `From an idea`: `2. What it
    is about`, `3. How it looks`, `4. Where it stops`.
  - `test_start_checks_every_step_and_focuses_the_first_gap`: no file and no title: pressing
    `Start the deck` posts nothing, says `Something above is missing.`, and focuses
    `new-file`.
  - `test_the_sheet_sends_what_the_wizard_sent`: the inputs of
    `test_a_new_existing_deck_is_a_route_card_a_level_card_and_an_upload` (`test_desk.py:270`)
    filled in the sheet give the same `(route, level, source, title)` and the same upload
    bytes.
  - `test_cancel_keeps_the_draft_for_the_session`: fill a title, `Cancel`, `New deck` again:
    the title box holds it.
  - `test_screen_new_still_opens_the_form`: a page opened at `?screen=new` shows Home with
    the sheet open.
  - `test_research_from_is_ticks`: with research on, `your sites (2)` and `the public web`
    are check boxes; `{tick: 'the public web'}` turns it off and the sent
    `research_from` has `web: false`.
  - `test_bring_in_a_deck_picks_then_brings`: two remembered decks: two pick cards, then
    `Bring it in` and `Cancel`; nothing is posted until `Bring it in`.
  - Moved controls: `test_back_a_step_and_another_way_to_begin_are_gone`: neither is in any
    snapshot's `buttons`; the route cards are in step 1.
- [ ] **Step 2: Run to fail:** `python3 -m unittest test_layout -v`.
- [ ] **Step 3: Implement.** `show('new')` maps to Home plus `openNew()`. `paintNew(fresh)`
  draws the sheet. Each builder drops its `card(...)` wrapper and returns its title and
  nodes; `startStep` splits into "How it looks" (brand, then the Options disclosure as a
  plain `details` with a 44px `summary`) and "Where it stops"; the aside becomes one `p.quiet`
  above the foot. `researchFromField` renders `fieldset.research-choices` (`legend`
  "Research from") with `StudioLists.tick`, and `.site-choices` for the sites. Update the 15
  journeys: drop each `{'click': 'Continue'}`; keep their assertions on the sheet's words.
- [ ] **Step 4: Run to pass:** `python3 -m unittest test_layout test_desk -v`.
- [ ] **Step 5: Commit:** "Start a deck from one numbered sheet, and bring a deck in by picking it".

## Task 8: Presentation Studio's deck screen, kept light

**Files:**
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js`
  (`deckIntro` :3540, `deckActions` :5679, `paintDeck` :5726, `outlinePanel` :4555,
  `paintReviewBar` :5440, the outline picture form :4440-4478, panel sub-headings in
  `researchPanel`, `buildPanel`, the revisions panel)
- Test: `studios/presentation/tests/test_layout.py`

- [ ] **Step 1: Write the failing tests** in `test_layout.py`, each through
  `self.deck_screen(path, steps, narrow=…)`:
  - `test_the_deck_opens_with_its_lede`: `shot['ledes'] == [run['sentence']]`, and the
    words before it in `shot['text']` are only the toolbar's.
  - `test_undo_sits_beside_the_lede`: a paused deck: `'Undo the last step'` is in
    `shot['buttons']` and not in `[c['name'] for c in shot['toolbar']]`; clicking it opens the
    Undo sheet.
  - `test_what_needs_you_comes_before_what_is_made`: a deck at a gate with build progress:
    in `shot['parts']`, the gate's card comes before `Slides taking shape`, which comes before
    `Where it is` and `Delete this deck`.
  - `test_the_direction_review_has_no_card_in_a_card`: at `gate:outline` with research and
    looks: `shot['nested'] == 0`; `What should change in the research?` labels a box whose
    form ends `Research again`, `Cancel`.
  - `test_a_phone_sends_marks_from_the_review_bar`: an item-by-item stop, `narrow: True`:
    the review bar holds the filled send; the toolbar has no filled control. On a desktop the
    toolbar holds it and the bar does not.
  - `test_a_slide_picture_can_be_cancelled`: the outline row's picture form has `Add the
    picture` then `Cancel`; `Cancel` clears what was chosen and posts nothing.
- [ ] **Step 2: Run to fail:** `python3 -m unittest test_layout -v`.
- [ ] **Step 3: Implement** the spec's deck-screen list. Keep every part's key, so focus and
  open disclosures are kept across redraws.
- [ ] **Step 4: Run to pass:** `python3 -m unittest test_layout test_desk test_review_levels -v`.
- [ ] **Step 5: Commit:** "Put what a deck needs from you first on its screen, and keep its send under the thumb on a phone".

## Task 9: Training Studio Home, detail, Status, Settings, Set-up and the index

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js` (`drawHome` :1720,
  `needsRow` :1610, `quietRow` :1636, `paintTraining` :3071, `drawStatus` :1996,
  `drawSettings` :2074, `alertsCard` :2023, the Brand skill card :8097, `paintSetup` :4068
  and "Checked for you" :3933, `drawIndex` :8197)
- Test: `studios/training/tests/test_layout.py`

**Interfaces (Produces):** `startCard()` ("Start a training") calling `openNew()`.

- [ ] **Step 1: Write the failing tests:**
  - `test_home_puts_what_needs_you_first_and_setup_after_ways_to_start`: `shot['ledes'] ==
    ['What needs you comes first, then trainings in progress, then ways to start one.']`;
    `shot['parts']` begins `['Needs you', 'In progress']`, with `'Start a training'` before
    `'Updates'` and `'Your other studios'`, and `'Finished'` after them.
  - `test_the_detail_leads_with_what_is_in_the_way_and_hides_empty_cards`: a training with
    one blocker and no warnings: `In the way` precedes `Files`; `No warnings.` is not in
    `shot['text']`.
  - `test_status_shows_the_check_first`; `test_settings_has_one_lede_and_one_versions_link`:
    `'See the versions'` appears once in `shot['buttons']`; `shot['filled'] == []`.
  - `test_the_index_downloads_from_its_toolbar`: `shot['toolbar'][0] == {'name': 'Download
    the index', 'filled': True, 'quiet': False}`; `shot['ledes'] == ['Everything this
    training made, with where each file is.']`.
  - `test_set_up_has_one_heading_per_card`: every `cardHeadings` entry has one tag.
- [ ] **Step 2: Run to fail:** `cd studios/training/tests && python3 -m unittest test_layout -v`.
- [ ] **Step 3: Implement** the spec's section 7 for these screens.
- [ ] **Step 4: Run to pass:** `python3 -m unittest test_layout test_desk -v`.
- [ ] **Step 5: Commit:** "Lay out Training Studio's Home, detail, Status, Settings and index in the order a person works".

## Task 10: Training Studio Trainings and Published

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js` (`trainingCard`
  :1755, `drawTrainings` :1772, `paintPublished` :8148, a `bulkDeleteSheet` beside the
  delete sheet :7284)
- Test: `studios/training/tests/test_layout.py`

**Interfaces (Produces):** `view.filters.trainings = {text, stands}`,
`view.filters.published`, `view.ticked.trainings: Set`.

- [ ] **Step 1: Write the failing tests**, as Task 6's with trainings:
  `test_trainings_filter_by_where_it_stands`, `test_a_phone_shows_search_and_a_filters_button`,
  `test_ticks_survive_filter_changes_and_the_bar_says_so`,
  `test_deleting_several_trainings_asks_first_and_carries_on_past_a_refusal` (button
  `Delete 3 trainings`, toast `Deleted 2 of 2 trainings.`),
  `test_published_is_a_table_with_one_open_per_row`. Also
  `test_a_conversation_mode_list_has_filters_too`: without the runner, the filter row shows
  and no `New training` is offered.
- [ ] **Step 2: Run to fail:** `python3 -m unittest test_layout -v`.
- [ ] **Step 3: Implement** with `StudioLists`; card titles become `h2.card-title`.
- [ ] **Step 4: Run to pass:** `python3 -m unittest test_layout test_desk test_runner_delete -v`.
- [ ] **Step 5: Commit:** "Give Training Studio's Trainings a filter row and a selection bar, and Published a table".

## Task 11: Training Studio's new-training sheet, the picture sheet and the research choice

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js` (`topicStep` :4450,
  `shapeStep` :4526, `startStep` :4641, `paintNew` :4703, `drawNew` :4736, `newButton`,
  `researchFields` :4328, `assetForm` :5948, `supplyAsset`, `drawSheet`)
- Test: `studios/training/tests/test_layout.py`; update the 28 `Continue` journeys and the
  `Back a step` journey at `test_desk.py:4276`

**Interfaces (Produces):** `openNew()`, `createStep(number, title, ...nodes)`,
`openPicture(found, index)` (the `picture` case of `drawSheet`).

- [ ] **Step 1: Write the failing tests:**
  - `test_new_training_is_one_sheet_in_numbered_steps`: `1. Learning goal`, `2. Materials`,
    `3. Research`, `4. Where it stops, and the assistant`; the sheet ends `Start the
    training` (filled), `Cancel`; the toolbar holds no `Continue`.
  - `test_ready_to_start_sits_above_start`: the `Ready to start` words come after step 4's
    and before `Start the training` in `shot['sheet']`.
  - `test_the_sheet_sends_what_the_wizard_sent`: the inputs of the existing start journey
    give the same `POST /api/trainings` body.
  - `test_cancel_keeps_the_draft_for_the_session` (replaces the `Back a step` journey).
  - `test_a_picture_is_added_in_its_own_sheet`: a deck waiting for a picture: the run
    screen's first part names it; `Add the picture` opens `Add a picture` with `1. The
    picture`, `2. What it shows`, `3. Where it came from, and any limit on its use`; the
    sheet's send posts the same body `supplyAsset` posted.
  - `test_research_from_is_ticks` as in Task 7.
- [ ] **Step 2: Run to fail:** `python3 -m unittest test_layout -v`.
- [ ] **Step 3: Implement** as Task 7, and the picture sheet. Update the journeys.
- [ ] **Step 4: Run to pass:** `python3 -m unittest test_layout test_desk test_runner_research_sites -v`.
- [ ] **Step 5: Commit:** "Start a training from one numbered sheet, and add a deck's picture in a sheet of its own".

## Task 12: Training Studio's combined review, run screen and gates, kept light

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js` (`reviewBar`
  :6204, `combinedReview` :6237, the marks :6336-6360, `runActions` :5772, `runIntro`
  :4939, `paintRun` :6364, the look actions :5855-5861, the copy conflict :5556-5570,
  `paintGate` :2516, `gateActions` :2478, the covered-gate callout :2414-2418,
  `paintOutline` :6622)
- Test: `studios/training/tests/test_layout.py`

- [ ] **Step 1: Write the failing tests:**
  - `test_the_primary_follows_the_marks`: at the first-drafts review on a desktop, nothing
    marked: `shot['toolbar'][0]['name'] == 'Approve the first drafts'` and filled; after
    `Needs changes in <item>`: `shot['toolbar'][0]['name'] == 'Send 1 request'`, filled, and
    `Approve the first drafts` quiet; the bar holds no button.
  - `test_a_phone_sends_from_the_bar_above_the_tab_bar`: `narrow: True`: the bar holds the
    one filled button; the toolbar holds none.
  - `test_looks_good_is_offered_at_every_width`: on a desktop `Looks good: <item>` is a
    control and marking it makes the bar read `1 of N looked at.`
  - `test_a_question_comes_before_the_review`: a run with a worker's question at a combined
    review: the question's words come before the review's card in `shot['text']`.
  - `test_a_copy_conflict_comes_before_the_steps`: `Use the Doc's version` comes before
    `Workers` and `Steps` in `shot['text']`.
  - `test_every_gate_has_one_lede`: for `gate:research` and `gate:blueprint`,
    `shot['ledes'] == ['Read <label>, then approve it or ask for changes.']` with the gate's
    label, lower-cased as the page writes it; `Ask for changes` is quiet.
  - `test_a_covered_gate_sends_you_to_the_review_from_its_toolbar`: `shot['toolbar'][0]`
    is `Request changes in the <review>`, filled.
  - `test_use_this_look_is_not_filled_beside_a_problem`.
- [ ] **Step 2: Run to fail:** `python3 -m unittest test_layout -v`.
- [ ] **Step 3: Implement** the spec's lists. Keep ids `send-requests` and
  `approve-combined-bar` on the controls that move.
- [ ] **Step 4: Turn the layout checks on everywhere.** In both studios' `test_desk.py`,
  `run_page` defaults to `layout=True`. Run each whole `test_desk`; a journey that now fails
  shows a screen this piece missed: fix the screen, not the check.
- [ ] **Step 5: Run to pass:** `python3 -m unittest test_layout test_desk test_review_levels -v`
  in `studios/training/tests`, and `python3 -m unittest test_layout test_desk -v` in
  `studios/presentation/tests`.
- [ ] **Step 6: Commit:** "Let the combined review's filled action follow the marks, and put what needs you first on the run screen".

## Task 13: Marketing Studio home and shared setup

**Files:**
- Modify: `core/studio_core/setup_web/index.html`, `core/studio_core/setup_web/app.js`
  (`labels` :36, `show` :76-113, `fillProfiles` :259-287, `renderSites` :211-219,
  `renderHome` :320-403, the `#check` listener :486-497), `core/studio_core/setup_web/home.css`,
  `tests/settings_page_harness.js`
- Create: `tests/test_layout_pass.py`
- Test: `tests/test_research_sites.py` (the harness's row reading), `tests/test_ui_consistency.py`

**Interfaces (Produces):** harness steps `{show: view}` (runs `show(view)`) and `{home:
snapshot}` (sets the page's snapshot and runs `renderHome()`); a snapshot may name `ids`,
and gets `hidden: {id: bool}` and `words: {id: text}` for them, and `cards`: for each
`#studio-list` child, `{studio, filled: [names], plain: [names], order: [class of each
child]}`.

- [ ] **Step 1: Write the failing tests** in `tests/test_layout_pass.py`:
  - `test_each_view_has_one_lede`: in `index.html`, each of `#home`, `#settings`,
    `#computer` holds exactly one `.lede`; their words are `Open a studio to start or
    continue your work.`, `New work in every studio starts with these choices.` and `Check the
    tools your studios need on this computer.`
  - `test_no_sheet_heading_inside_a_card`: no `sheet-part` class in `index.html` or
    `app.js`; every `section.card` in `index.html` has one heading element.
  - `test_check_computer_is_the_toolbar_primary_on_this_computer`: `#check` sits inside
    `.toolbar-actions`; `{show: 'computer'}` leaves it visible, `{show: 'home'}` and `{show:
    'settings'}` hide it.
  - `test_installations_live_on_this_computer`: superseded. The owner decided on
    2026-10-27 that `#installations` stays in Shared settings; the settings form has one
    submit button, `#save`.
  - `test_first_run_setup_has_one_title_per_step`: with `setup = true`, `#step-label` and
    `#settings-title` are hidden; the workflow steps read `You and your assistant`, `Where
    your work lives`, `Brand and delivery`; `#settings-intro` reads `Set up once, and every
    studio starts with these choices.`
  - `test_a_card_that_needs_connect_fills_connect`: a studio with `workspace.connect`: its
    card's `filled == ['Connect']` and `plain == ['Open Blog Studio']`, with Connect first;
    another studio's `filled == ['Open Presentation Studio']`.
  - `test_the_studio_status_is_a_state_with_a_bead`: each card's `order` holds `state` and
    no `studio-status`; the tile has class `studio-symbol`.
  - In `tests/test_ui_consistency.py`, `test_home_css_draws_no_shared_control`: no
    selector in `home.css` names `studio-icon`, `studio-status::before` or styles
    `site-row` with `border` or `padding`.
  - Moved controls: `test_moved_setup_controls_are_reachable`: `#check`,
    `#review-level`, `#model-profiles`, `#output` and each card's Connect exist and
    are shown on their new view.
- [ ] **Step 2: Run to fail:** `PYTHONPATH=.:tests python3 -m unittest tests.test_layout_pass tests.test_ui_consistency tests.test_research_sites -v`.
- [ ] **Step 3: Implement** the spec's section 8. Split each `.setup-part` into a card with
  `h3.card-title` and its `data-step`; profiles become `fieldset.paper.profile-card` with
  `legend.field-label`; move `#check` into `.toolbar-actions` (hidden unless the view is
  `computer`); leave `#installations` in Shared settings (owner, 2026-10-27); `.studio-icon` → `.studio-symbol` with
  an `icon` class on its `svg`; the status line through `stateLine`; research sites as a
  `table.table` of `tr.site-row`, the site in `td[data-label="Site"]`, Remove in the last
  `td`; `#home`, `#settings`, `#computer` and `.setup-form` take `class="stack"` and lose
  their `home.css` rule; spacing to 1.1rem and 0.6rem. In the harness, read a row's text from
  `children[0]` and its button as `children[1].children[0]`.
- [ ] **Step 4: Run to pass:** the command of Step 2, then
  `PYTHONPATH=.:tests python3 -m unittest tests.test_shared_setup tests.test_home -v`.
- [ ] **Step 5: Commit:** "Give Marketing Studio's home and shared setup one title per step, one save, and the shared controls".

## Task 14: Docs

**Files:**
- Modify: `docs/design/golden-gate.md` (Layout rules intro; take new screenshots only if the
  owner asks), `README.md:288` (stays "Shared settings → Studio installations", owner
  2026-10-27), `studios/presentation/docs/runner.md:45` (New deck is a sheet in
  numbered steps), `studios/presentation/docs/capabilities.md:11,18` (the step names),
  `studios/training/docs/runner.md:106,144,238` (the four steps; Research from as ticks),
  `studios/blog/CHANGELOG.md` (Unreleased: "Controls are at least 44px tall, and the
  selection bar's styles come from the shared stylesheet.")
- [ ] **Step 1:** Update each place above so it says what the page does now. Grep for every
  label in the spec's "Moved controls" tables across `README.md`, `docs/`,
  `studios/*/README.md`, `studios/*/docs/` and the studios' guidance, and fix only what is now
  untrue. A guidance change here is words only: run `python3
  studios/training/skills/training-studio/scripts/validate_package.py`, `python3
  studios/presentation/skills/presentation-studio/scripts/validate_package.py` and `python3
  studios/blog/scripts/measure_guidance.py --check`.
- [ ] **Step 2: Commit:** "Document the layout pass in every studio's guide".

## Task 15: The full check

- [ ] **Step 1: Run once, from a clean tree:**
  - Root: `PYTHONPATH=.:tests python3 -m unittest discover -s tests -v`.
  - Presentation: `cd studios/presentation && python3 scripts/ci/run_tests.py --jobs 4 && python3 skills/presentation-studio/scripts/validate_package.py`.
  - Training: `cd studios/training && python3 scripts/ci/run_tests.py --jobs 4 && python3 skills/training-studio/scripts/validate_package.py`.
  - Blog: `python3 studios/blog/scripts/ci/run_tests.py --jobs 6`, `node studios/blog/scripts/ci/check-management.cjs`,
    `cd studios/blog && ruff format --check . && ruff check .`.
  - Prefer the shared Tart runner on macOS for the whole suite:
    `bash scripts/ci/tart-macos.sh --dry-run`, then without `--dry-run`.
  - Compare any failure with a clean `git archive origin/main` export before calling it
    pre-existing.
- [ ] **Step 2: Look at it.** Start each studio against disposable data (temporary `HOME`,
  `STUDIOS_CONFIG`, `PRESENTATION_STUDIO_DATA`, synthetic decks and trainings, no assistant on
  `PATH`) and take before-and-after screenshots at 1280px and 390px of Home, the list, the new
  sheet, a stop and Settings in each studio, and Marketing Studio's three views. Check by eye:
  one filled button, nothing under the tab bar, no text running out of a control.
- [ ] **Step 3:** Write the pull request body with the spec's three "Moved controls" tables
  and the test plan, then commit anything left: "Finish the layout pass".
