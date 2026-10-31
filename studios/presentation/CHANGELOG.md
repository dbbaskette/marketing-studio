# Changelog

Releases are published from `VERSION`. Each entry says what changes for people
making decks first, then what changes for maintainers.

## Unreleased

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
