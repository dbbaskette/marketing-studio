# Changelog

Releases are published from `VERSION`. Each entry says what changes for people
making decks first, then what changes for maintainers.

## Unreleased

- **Every delivery keeps its receipt, and the desk keeps your focus and your edits.**
  The **Delivered** card lists every revision with its format and time, and opens
  each one: **Open in Google Slides**, or **Download revision N** while that
  PowerPoint file is still kept beside the deck. A Google delivery no longer takes
  the last PowerPoint file away. **Send to Google Slides** asks first, in a sheet
  that says what goes and as which revision, on the desk and on a gated deck's
  screen alike; both list every revision. The card also says whether the
  Document Library kept the deck, from which deck revision, and that the library
  counts its own revisions. Home and Decks say where a deck went in words, with
  its link as a button. **Add from library** never offers the deck's own
  delivery. **Keep in library** now keeps pasted text too. After **Skip**,
  **Apply**, **Deliver** and **Add the pasted text** the focus lands beside what
  changed, and each Apply and Skip is named for its proposal. Finishing keeps
  the slide at its width on a desktop and opens as a sheet on a phone, its
  heading focused and Tab kept inside it; Escape closes it. Toasts sit over the
  sidebar's foot on a desktop and over the bar of screens on a phone, clear of
  the page's controls. Opening **Brand check** no longer turns
  warnings into things that wait for you. A change on the Outline tab that is
  not saved is listed before you deliver, said on its slide, kept when the
  outline is read again, and **Deliver** waits until you save or discard it.
  The Outline tab has its own sentence and names **Move up**, **Move down** and
  **Remove** on each row.

  For maintainers: run['revisions'] entries record `sha256`;
  `deliver.receipt_file` and `deliver.receipts` read them, `/api/download` takes
  `revision`, and `deliver.record`/`again` leave `deck.pptx` in place.
  `deliver_again` keeps the deck in the library as `_deliver` does. The desk view
  adds `receipts` and `own_library`, and `desk_library` refuses the deck's own
  document. `/api/desk-source` takes `library` with pasted text. #257.

- **The slide text and the look pause say what they ask, and drop nothing.**
  **Approve text & design deck** is the toolbar's filled action. A change typed
  in **Changes to slide text** is never lost: Approve asks whether to send it
  first or approve without it. Each slide's title, points and speaker notes can
  be corrected in place and approved with no assistant job, and **What the
  research found** is folded above the text. The looks are a proper radio group,
  with the brand's default chosen until you pick another. Home, Decks, the toast
  and the header say the same stage: "Waiting for you to approve the slide
  text.", "Waiting for you to pick the look.", "Ready to deliver." and
  Delivered. A deck shows one waiting toast at a time, and none once it is
  decided. The Home badge counts decks only, as the greeting does.

  For maintainers: `Drafting.slideContent` (shared) takes `edits`, `onEdit` and
  `toolbar`, and its node has `decide`; `DeckPanels.lookPicker` (shared) has a
  roving tabindex and `preselect`. The engine's `_waiting_words` gives a desk
  deck's waiting sentence. #256.

- **A library document beside your document stays a supporting source.** When
  a deck from a document has documents chosen from the library, the outline is
  written from your document alone. The library documents go to it under their
  own label, as supporting sources, and the classification lists only your
  document. A library choice that is missing or was removed from the library is
  refused before anything is made. New deck takes at most 40 documents from the
  library; at 40, **Add from library** waits and says why.

  For maintainers: `outline._document_texts` reads `intake.theirs`, and
  `_supporting_texts` adds the pins as "Supporting source: …" inputs. The
  engine's `_show_classify` lists `intake.theirs`. `studio_core.document_library.context`
  gains `picks` (the shape alone) and `snapshots` (each pick read and checked),
  and `pin` uses them. The engine reads every pick before `decks.create`, and
  `/api/decks` answers 400 for a malformed pick. `research.js` takes an optional
  `libraryFull` adapter hook. Part of #255.

- **Research choices are checkboxes that say what will happen.** **Research
  first** is now a checkbox, as other independent choices on a form are, and a
  screen reader announces it as one. Under **Search for additional external
  sources**, the line now says what research will read as the box stands:
  "Only your sources are used. Tick to also search the web." when it is not
  ticked, and that the public web, or only your approved sites, is searched too
  when it is. It no longer reads as a second, contradicting option.

  For maintainers: `settingsStep` draws Research first with `StudioLists.tick`
  (`research-first`). `ui-kit/research.js` takes an optional `policyHint(state)`
  adapter hook for that line; studios that do not pass it keep the shared
  summary. Closes the Presentation Studio row of `docs/design/form-choice-audit.md`
  for Research first. Part of #255.

- **One name for each kind of deck, and for its brand.** Home's **Start a
  deck**, a deck's header and the Decks filter now say **From an idea**, **From
  a document** and **From an existing deck**, the names New deck asks with (An
  idea, A document, An existing deck). "Start from scratch", "From scratch" and
  "Redesign an existing deck" are gone; an existing deck covers every level,
  not only a redesign. The look and the look pause name the brand as New deck
  does, for example "Made in Example Co (light)", not by its ID.

  For maintainers: `ROUTES` in `app.js` holds the one name per route, and
  `routeWords` and the Decks filter read it. `madeIn(brand, variant, fallback)`
  names a brand from Set-up's brand list and falls back to the runner's
  `made_in`; the deck is drawn again when Set-up's brands arrive after it.
  Part of #255.

- **The start's sources match the desk's Sources card.** With **Research
  first**, **Your sources** on New deck now offers **Add from library**, and a
  file chosen there offers **Keep in library** (the default) or **Only this
  project**, as the desk does. A library document chosen at the start is
  copied into the deck as a source when it starts, and counts as research's
  own material, so no other source is needed. On the desk, the Sources card
  lists every source research and the words jobs read: the sources given at
  the start say "given at the start, for research", and the card's count
  matches the Research card's. The words jobs and speaker notes now read those
  sources too. A library document beside a deck's own document is never taken
  for it, or classified as it.

  For maintainers: `/api/decks` takes `library` ([{id, revision}]) with a
  researched deck from an idea or a document. It is pinned with `context.pin`
  before the deck runs, all or none, and is part of the start's receipt.
  `/api/research-sources` goes through `runner/source_keep.py`, which takes
  `keep` with a file capture and `library-keep`, as Training Studio's does. It
  uses `desk_actions.library_upload`, so the start and the desk keep one
  library document for one file. The desk view's `sources` adds
  `research_input` entries from `research_sources.document_entries`.
  `intake.document_taken` and `classify_work` skip library pins.
  `ui-kit/research.js` takes two optional adapter hooks, `library` (an Add
  from library button) and `extra` (a node under the list); other studios are
  unchanged. Part of #255.

- **The New deck heading hides what scrolls under it.** The sheet's sticky
  heading was slightly see-through, left a gap above it, and was drawn under
  choices such as **Pick it when the samples are drawn**, so text showed
  through it at every width. It is now opaque in light and dark, reaches the
  sheet's top and sides, and sits above those choices. Every sheet with a
  heading, in Blog Studio and Training Studio too, gets the same fix.

  For maintainers: `ui-kit/style.css` adds `.sheet > .sheet-heading:first-child`
  (negative `top` and margins equal to the sheet's padding, `z-index: 2` over
  `.seg-option`, and the sheet fill over `--paper`). The `.sheet-heading` rule
  itself is unchanged. Part of #255.

- **Start a deck with Research first again.** With **Research first** on,
  **Start** did nothing, for a deck from an idea or from a document, with
  sources or without. It now starts the deck, and its research runs. With no
  readable sources and no additional external search, the sheet says "Add
  readable sources or allow additional external search before starting." under
  the sources and puts the focus in the box for links.

  For maintainers: the start sheet checked research in a problem line that only
  the old research chooser drew. The shared source editor now has it beneath
  it. `page_harness.js` loads `research.js` when a plan says `research: true`,
  as the real page always does. It also finds boxes inside their labels, has
  `replaceWith`, and its snapshots say `focusKey`. Part of #255.

- **A delivered deck's PDF in the Document Library.** After delivery, the
  library keeps the deck's PDF beside its slide Markdown. The PDF is the one
  Harness Slides already rendered of the delivered deck, and drew its slide
  pictures from, when the deck was last previewed. It is kept, and the Sources
  card says **PDF saved**, only when it still matches the deck delivered.
  Nothing is rendered, uploaded or installed for it. Otherwise the card says
  **PDF needs export** and why: the deck was delivered on another computer, the
  deck is your own at **Selected changes**, or the PDF changed. **Keep in
  library again** uses this computer's files only. It uploads nothing to Google
  and runs no slides tool or assistant.

  For maintainers: `deliver.json` records `deck_sha256`, and each whole-deck
  round records `pdf`, the hash of the preview's `deck.pdf`.
  `library_keep.rendered_pdf` checks both against the last round, the
  preview's `preview.json` and its `deck.pptx`. `Library.retain` takes
  `pdf={'state': 'saved', 'data': ...}` and keeps it as `content.pdf`. The
  slides stand-in's render is now a PDF of its deck, with `%%EOF`. Closes #237.

- **Keep in library or Only this project, for a file added on the desk.** The
  Sources card's **Keep the file** choice comes before the file picker.
  **Keep in library** is the default and also saves the file in the Document
  Library on this computer, for any studio to use. **Only this project** keeps
  it with the deck only. The deck's own copy is the same either way, and
  neither choice shares anything. If the library can't keep the file, the card
  says so and the deck keeps the source. Pasted text stays with the deck.

  For maintainers: `/api/desk-source` takes `library` (true or false) with a
  file, and the answer's `library_upload` is `{state: 'kept', id, revision}` or
  `{state: 'failed', problem}`. Presentation Studio's part of #238.

- **Start a deck from its source and goal, and see its stops before Start.**
  New deck now asks what the deck starts from, with the brief, the document or
  the deck itself, then the audience and goal, then research and settings. The
  brand, variant, output and assistant start as your defaults under **Brand,
  output and assistant**. **What happens after Start** lists, from your
  choices, research when asked for, **Approve the slide text** wherever slide
  text is drafted, the look to pick or the brand's default, then reviewing the
  deck and delivering. The "stops once" promise is gone from the sheet and from
  Home. Changing the kind of deck keeps everything typed and chosen, research
  and where it may look included, and each kind keeps its own file. Saved decks
  keep their decisions and run nothing again. A document's research sources
  still say the document is included, and the document picker still takes PDF
  files.

  For maintainers: the start-form code in `deck-desk.js` (`start`,
  `sourceStep`, `goalStep`, `settingsStep`, `roadmap`) builds the list from the
  route, level, research, reading and look; `chooseRoute` in `app.js` no longer
  resets research and keeps each kind's file and link.

- **Review and change one slide at a time on the desk.** The Slides tab is a
  workbench instead of one long form. A navigator lists every slide with its
  picture, number, title and what it needs, and reaches any slide at once on a
  desktop or a phone. The slide chosen shows its picture first, then what the
  brand check and the review found on it, each once, with a proposed fix to
  apply (priced first) or skip, then its words, speaker notes and note; its
  caveat and source are folded. A short summary says what blocks delivery, what
  waits for you (including slides a stopped whole-deck note did not redraw) and
  what is only worth a look, each linked to its slide, and what Deliver will
  use. The whole-deck note is a folded, secondary action that says it redraws
  every section. The slide chosen and words not yet saved stay through the
  Outline tab, Finishing, History, Deliver and a reload. A synthetic eight-slide
  deck at 390px went from about 11,350px to about 2,650px tall. Approval,
  delivery, revision binding and every redraw's scope and price are unchanged.

  For maintainers: the workbench is drawn in `deck-desk.js` (`slideParts`,
  `summaryPart`, `navigatorPart`, `slideCard`, `foundOn`, `marksOf`) from the
  desk view alone; the slide chosen is kept per deck and in `history.state`
  (`deskSlide`, `deskNumber`). No route or server gate changed.
