# Changelog

Unreleased: on the slide desk **Slides** and **Outline** sit at the start of their row, next to the slides; **Previous** and **Next** share one row above the navigator; and the Sources panel is wide enough for its file field.

Unreleased: a deck's page leads with the Brief, Plan, Make, Ship arc and **Your move**. Slide text is reviewed in the middle of the screen with the assistant's rail beside it; the slide desk keeps its side panel and shows the arc in a band above.

Unreleased: **Search and jump** (Cmd or Ctrl+K) and a Light, Dark or Auto appearance sit at the foot of the sidebar.

Unreleased: New deck's three steps each say what was chosen and open when pressed, as Training Studio's do, and the third step's heading matches its name. A deck now needs Harness Slides 0.17.0 or newer.

## Unreleased — 4.15.0

Completed research sections expose saved read-only prose before final checking. Previews name their revision and assigned sources and remain ineligible for delivery. Queued concerns save privately across reloads without changing evidence or starting work; apply actual changes through the existing explicit refresh/impact flow. Timing separates the first readable section from the checked result.

## Unreleased — 4.14.1

Idle desks check a compact change signal before reading content again. Active work keeps its existing cadence; focus and reconnect catch up immediately. Incomplete metadata checks fall back to full reads, and connection failures back off.

## Unreleased — 4.14.0

Slide-text review shows one slide at a time with a compact picker and collapsed speaker notes. Corrections, feedback and selection save privately across reloads without starting work. Earlier corrections remain available when the outline changes; approval uses only the exact validated current text.

## Unreleased — 4.13.0

New work warns and continues at its project spending amount by default. Shared settings can choose Stop and ask; saved work has an explicit, stale-safe spending choice. Old tasks keep hard-stop behavior and Carry on. Warning mode supplies a $5 budget per job, keeps smaller Quick-scan budgets and time limits, records crossings once in Activity and shows them on the desk and home. Dollar enforcement and reporting depend on the assistant. Policy saves start no work or new research.

## Unreleased — 4.12.1

Saved work publishes compact metadata for Marketing Studio’s Needs you, In progress and Recent work overview. Direct resume opens the saved editing/decision context. Metadata browsing starts no studio or provider work.

## Unreleased — 4.12.0

New section workflows preview affected research before refresh. Added sources can target selected sections; changed or removed inputs require wider invalidation. Retained investigator packets and drafts are revalidated, and assembled research still needs a fresh independent check. Wording, notes-only edits and existing section updates keep their direct routes.

## Unreleased — 4.11.0

New outline-first work keeps section contributions across retries, combines at most three at once, and gives only a timed-out contribution more time. A short final author reads the contributions; the supported independent whole-report check still gates use. Existing saved flows retain their schemas and helper versions.

Releases are published from `VERSION`. Each entry says what changes for people
making decks first, then what changes for maintainers.

## Unreleased

- New researched desk decks use one bounded saved Quick-profile scan and an editable
  slide story before research. Save without model work; approve exact retained sections,
  messages and questions before independently checked research and slide-text drafting.
  Stop/timeout keeps a usable provisional story without escalation. Existing scripts,
  selected edits and saved older flows keep their direct routes. New records use schema 5,
  refused by older runtimes. Slide-text, look and delivery decisions remain explicit.
- Share provisional-scope validation and excerpt limits with Training Studio. Research
  source permissions and the pinned companion protocol remain unchanged.

- **New deck saves your place in three real pages.** Source, Audience, and Research and
  review keep answers and source pins through Back, Next, reload and Save and close.
  Only Start begins work. Explicit discard clears the private form and keeps captured
  sources. Creation sheets have an opaque, centered form and a visible action footer.
  The desk brings the selected slide forward, folds optional status details, and puts
  secondary phone actions under More.

- **Editing keeps your place.** Slide status refreshes and autosave preserve keyboard focus
  and the caret, and composition input finishes before a deferred refresh. Library choices
  keep their confirmation in reach on a phone. The Activity log distinguishes the first
  saved result, recorded assistant/check time, queue time and time waiting for you.

- **Choose a model and reasoning level for each kind of work.** Settings now offer six
  kinds instead of Quick, Main and Complex: Quick, Research, Combining, Checking, Writing
  and Fixing. Classifying, extracting and the outline stay on Quick, research runs on
  Research and Combining, the deck review on Checking, slides and ordinary repairs on
  Writing, and escalated repairs on Fixing. Settings saved before keep their choices; until
  you save the new kinds, Research, Combining and Checking start from Main's model at
  medium reasoning. Decks already started keep the models they began with.

- **Research assistants get their evidence accepted sooner (#303).** Each research
  assistant is now told, up front, every field each source needs: the source's ID, file,
  exact origin and permission are filled in for it, and it is told what to add (who
  published the source, whether its capture is full or partial, and its date only when
  the source states one). When it hands back evidence with problems, it is told all of
  them in one short list instead of one at a time, so research takes fewer assistant
  turns. The assistant that combines the evidence is told the exact shape of the report
  and brief it returns, and the independent check is told what each part of its review
  takes; each is told everything to correct at once too, and the check now corrects its
  review inside its own job instead of the research failing afterwards. What is accepted
  is unchanged: nothing Harness Research refuses is accepted.
  Maintainers: `source_outline` (from `research_contract.source_outline`, read from the
  pinned helper's schema) is in each investigator's and serial author's research-task
  input, with `synthesis_outline` for the synthesis and serial author and
  `review_outline` for the review, and the job's text says to build from them. The worker tools'
  research-json check (`research_contract.check_json`) gathers every studio check and
  `packet_problems` (evidence) or `compose_shape` and `synthesis_problems` (synthesis)
  before the pinned helper, which runs as before when they find nothing; a review job's
  artifact now carries its `review_template`, and `review_problems` checks it in the job.
  See `docs/research-synthesis.md`.

- **See what the assistant is doing, and what it did (#294).** Each assistant job
  working now shows its name, when it started and its latest action as "Now: …", and
  **Show activity** opens everything it has done so far, newest first, with times; the
  research panel shows the same while it collects evidence, combines findings and
  checks sources. A deck's **Activity log**, on its screen and on the desk, lists each
  finished job newest first with how it ended (finished, failed, stopped, out of time
  or a limit) and its lines, whether the deck is still working, finished or stopped. A
  deck with none says "No activity recorded yet." Only the plain lines are kept: never
  the brief, sources or the assistant's raw events.
  Maintainers: `studio_core.activity_log` keeps a running job's lines with their times
  (200 a job) and appends each ended job to the deck's `work/activity-log.jsonl` (the
  latest 200 jobs, never committed) under the files lock, after the job, and a log that
  cannot be written never changes how the job ends. `run.workers[]` now carries `now` and
  `count` in place of `lines`, so a poll stays small: `GET /api/activity?path=` reads the
  log's headers, `&entry=` one finished job's lines and `&job=&since=` one running job's
  lines from the `since`th on, which the page asks for only while its Show activity is open.
  `ui-kit/activity.js` draws the lines and the log for every studio, keeping focus, what is
  open and the list's scroll as the page redraws. The event readers moved from
  `shared_runner.agents` to `studio_core.agent_events`. Jobs after research that finished
  in parallel show in Assistant jobs now again, not in the "Research is ready" panel.

- **A Google Slides link in the shared source panel now reads (#292).**
  Decks were read through the Google Slides API, which a gcloud sign-in cannot call
  without a quota project, so pasting a deck's link failed with "lacks access" even
  when Google Drive could open it. Now the deck is exported through Google Drive as
  PowerPoint and its titles, text, tables, groups and speaker notes are read slide by
  slide, in presentation order. Slide choices, the 1–200 slide limit and the
  "changed while being read" refusal stay as they were. A source saved earlier still
  opens from its stored capture; changing its slide choice matches the earlier slides
  only while the deck is unchanged, and otherwise says so and keeps the earlier
  capture. When Google refuses, the message says why: an API not enabled for the
  sign-in's project, a sign-in missing Drive access (with the command to fix it), a
  file this account cannot open, or a deck larger than the 10 MB Google Drive
  exports, which is better uploaded as a PDF.
  Maintainers: `studio_core.pptx_slides` reads the export with `zipfile` and expat
  (size-capped parts, no DTDs or entities); `google_reference.capture` takes
  `previous` and `slide_choice` resolves `slide-<n>-<digest>`, `slide-<n>` and
  earlier identities; `google_api.Client.export_presentation` replaces
  `presentation`, `slides.googleapis.com` is no longer an allowed destination, and
  `refusal` reads a 403's `error.status`, `errors[].reason` and `details[].reason`.
  A failed slide or tab re-choice in `research_sources` now keeps the ready capture.

- **Research from a source with extra spaces finishes (#295).** When a source's
  text had double or trailing spaces or several blank lines, as Google Slides decks
  often do, research stopped after synthesis with "harness-research refused: Source …
  capture differs from the accepted asset inventory". The source was registered with
  Harness Research as it came, while the assistant read and quoted a tidied copy. Now
  the tidied text is registered, so the two match. A deck that stopped this way
  recovers with **Try again**: its checked investigations are kept, and only
  synthesis and the independent review run again. Sources that were already tidy are
  registered unchanged.
  Maintainers: `research_session.Workflow.asset` registers and offers
  `capture_text(text, kept)`, which is `shared_runner.worker_tools.tidy(text)` unless
  that source's own kept copies (`kept_copies`, at
  `sources/collection/<area>/<attempt>/<capture file>`) hold only the untidied text.
  Registration runs on every start, and Harness Research's `asset source` re-hashes
  `capture_sha256`; intake, the input fingerprint, the research basis and capture
  file names still come from the text as it came.

## 4.9.0 — 2026-11-03

- **Released with Marketing Studio 4.6.0.** Installs pin Harness Research 1.1.0 and
  Harness Slides 0.16.0; the brand skill needs 0.14.0 or newer. Presentation Studio
  4.9.0; guidance needs runtime 4.9.0. This changelog was started on 2026-10-30, so it
  lists the changes since then; the desk and the other changes since Presentation
  Studio 4.5.0 are summarised in Marketing Studio's
  [release notes](../../docs/release-notes.md).

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
