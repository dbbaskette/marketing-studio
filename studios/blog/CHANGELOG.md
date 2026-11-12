# Changelog

Unreleased: links can be added from a file. Under **Add a source**, **Web link**, **Or add every link in a file** takes a text, Markdown, CSV or saved web page file and reads each public https link in it as a source for this blog, one after another. A page that cannot be read does not stop the others, and the page lists which were not added. A blog still takes up to 20 files.

Unreleased: while a check runs, one status box says what you are waiting on. It names the check, which step it is in (the copy edit, then the wording check), what the assistant is doing this moment with **Show activity**, and **Stop**. The sentence above the draft, the separate activity lines and the long text in the band at the top give way to it, so the same status is no longer said in several places.

Unreleased: **Finish this post**, at the top of Finishing, runs the usual pass in one go. Copy edit and more human-sounding wording (at the strength kept for the blog, medium the first time) are marked in your text as one review beside the Quick check, and a check of your claims against your sources follows; a draft with no sources skips that last step. Every tool still runs on its own.

Unreleased: the desk puts the writing first. With a draft to read and nothing pressing, the progress band is one quiet row. The toolbar has one filled action, **Finishing**, the only door to the finishing tools: **Polish** beside the view switch is gone. Copy, Download, the Google Doc actions and Mark as published are under **Share**; **Review changes to send** stays visible for a linked Doc.

Unreleased: no writing, research or finishing step is ended for how long it takes, because ending one discards its work. **Step time limit** is gone from Settings and a saved number is kept and ignored; a step runs until it finishes or you press **Stop**. Finding a published post's text keeps its own short limit.

Unreleased: Blog Studio checks whether Claude Code is signed in. **Status → Check this computer** now says **signed in** or **not signed in** for Claude Code, as it does for Codex, with `claude auth login` as the fix. A step that fails asks the assistant the same question: a signed-out assistant is named as the cause with the command that signs it in, and a signed-in one says so and points at its usage or rate limit.

Unreleased: the assistant has 50% more time before a step is stopped. A step's time limit for a new blog starts at 15 minutes, not 10, and **Ask Codex to find the post's text** and a library document's analysis have 4.5 minutes, not 3. A limit you already saved in Settings keeps its value.

Unreleased: **Verify in the Doc again** reads the Google Doc once more for the last send and says whether it still holds what was sent, or how many suggestions are now pending, accepted and rejected. It is offered on the send's receipt and, as **Verify the last send**, in the toolbar's Google Doc menu, also after a reload. Nothing is sent and the record of the send does not change.

Unreleased: a post's own GEO review now waits until the fixes in your text are accepted or rejected, and runs when the last one is decided, so it reads the post as you left it and proposes nothing those changes already made. **Run GEO review** still runs one at any time.

Unreleased: the desk and Review mode say where the GEO review stands, under the arc, and **Show GEO proposals** opens them in Finishing from either. **Open Finishing** now works from Review mode, and Review mode's move is the fixes still to decide.

Unreleased: after a send to the Google Doc, the receipt says what reading the Doc back found: when it was read, how many suggestions are pending in it and how many comments were found.

Unreleased: bringing in a Google Doc or a published page says so at once, in a sheet that names the steps (read it, open it on the desk, then the first pass) and puts itself away when the desk opens. While a check runs, the desk's card says what is being checked and that nothing is asked of you, in the studio's colour; work under way is no longer shown in the amber that means your move.

Unreleased: accepting or rejecting a fix in review keeps the page where it is. Focus moves to the next fix without scrolling, the page moves only when that fix is off the screen, and it never jumps back to the count at the top.

Unreleased: in review, the folded list of pattern findings is named **Quick check** and says it is a second, optional pass. **Sounds human** now names only the assistant's rewrites marked in the text.

Unreleased: Quick check leaves tables and horizontal rules out, so a table's rule of hyphens, its pipes and its repeated cell words are no longer flagged. A finding you dismissed stays dismissed when a fix changes the rest of its sentence.

Unreleased: the desk's view switch, **Go to section** and **Polish**, **Sources** and **Outline** share one row, with what the chosen view is for under it, so the draft starts higher. The arc stays on Make while the draft is read and polished and reaches Ship in Finishing, and **Your move** no longer fades in each time the desk is drawn again.

## Unreleased — 4.10.1

Before a check has run, **Your move** on the desk is the check itself and starts it. The roadmap across the top of a desk is drawn as a route: tinted as far as the work has come, with numbered marks, a line under each phase saying what it is, and a line that moves while the assistant works; it no longer collapses on a phone. Page scripts and styles are compressed and reused instead of downloaded on every open. On Marketing Studio's home an unfinished blog is listed as in progress, not as waiting on you.

Saved work publishes compact metadata for Marketing Studio’s Needs you, In progress and Recent work overview. Direct resume opens the saved editing/decision context. Metadata browsing starts no studio or provider work.

Releases are published from `skills/blog-studio/VERSION`. Each entry says what
changes for authors first, then what changes for maintainers.

## Unreleased

- **The desk says where the post is and what is yours.** A band above the draft shows the Brief, Plan, Make, Ship arc and **Your move**. **Full desk** is now **Edit everything**, and a line under the view switch says what each view is for.
- **Search and jump, and a chosen appearance.** Press Cmd or Ctrl+K to go to a screen or press a toolbar action by typing. **Light**, **Dark** or **Auto** at the foot of the sidebar sets the look of every studio.
- **New blog shows the same steps as the other studios.** The two steps sit in the shared step row: each says what you chose in it, the first shows a tick once it is complete, and pressing a step opens it. The first step's button is **Next**, and the second has **Back** beside **Start**.
- **For maintainers: the page runs on the shared loopback server.** Blog Studio's page is now served by `studio_core.server`'s server and handler, as the other studios' pages are. Its request checks, Content-Security-Policy, body limits, timeouts, one-at-a-time workspace access, routes and error messages are unchanged; nothing changes for authors.
- **See time to a saved result.** The existing private Activity log records operation
  boundaries and distinguishes saved intermediate results from final approval. Missing
  timings stay unknown; reading progress starts no assistant work.

- **Choose a model and reasoning level for each kind of work.** Settings now offer six
  kinds instead of Quick, Main and Complex: Quick, Research, Combining, Checking, Writing
  and Fixing. Blog Studio's research rounds run on Research, combining them on Combining,
  the draft review, fact check, feedback and GEO review on Checking, and returning a review
  to its draft on Fixing. Settings saved before keep their choices; until you save the new
  kinds, Research, Combining and Checking start from Main's model at medium reasoning, so
  research and checks are faster. Blogs already started keep the models they began with.

- **The Activity log can never change how a job ended, and the keyboard keeps its place
  (follow-up to #300).** A workspace that could not be read or locked while a job was
  being logged could turn a finished job into a failed one, or replace why a job failed,
  so **Try again with more time** and what the assistant said went missing. Now only the
  log entry is lost. A Codex failure whose reason is plain text is read as it came. On
  the angles step, the desk's Outline tab, a start's progress and the desk's side column,
  which are drawn again on each poll, the keyboard focus stays on Show activity or the
  Activity log, and a card just opened stays open.
  Maintainers: `blog_activity.Running.end` builds and writes the entry inside one
  `except Exception`, as Training Studio and Presentation Studio do; `blog_worker.Events`
  reads Codex's error lines inside the guard around `reader.feed`; `sPage` and the desk's
  side-column redraw keep the focus by `data-key` and each `details[data-key]`'s open state
  as the page shows it (`sFocusHeld`, `sFocusAgain` in runner.js).

- **Research investigators get their evidence accepted sooner (#303).** Each research
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
  Maintainers: `research_session` adds `source_outline` (from
  `research_contract.source_outline`, read from the pinned helper's schema) to each
  investigator's payload, `synthesis_outline` to the synthesis payload and
  `review_outline` to the review payload, and `research_text.Transport` returns
  `validation_error` as a bulleted list and checks a review against its
  `review_template` (`research_contract.review_problems`). `research_contract.check_json` gathers every studio check and
  `packet_problems` (evidence) or `compose_shape` and `synthesis_problems` (synthesis)
  before the pinned helper; see
  `docs/research-synthesis.md`.

- **See what the assistant is doing, and keep an Activity log (#294).** While a job
  runs, Blog Studio now shows what its assistant is doing as **Now: …** ("Searching the
  web: …", "Handing back its answer"), and **Show activity** lists every line so far,
  newest first, with times: on the desk, in the research panel, on a step-by-step run, on
  a GEO report being written, and while the assistant finds a page's text or suggests
  angles. Each blog's **Activity log** (on the desk and its run), and each GEO report's,
  keeps every finished job, how it ended and what it did; work for no blog is in the log on
  Status. Results, time limits, Stop, usage and error messages are as they were. The log
  stays on this computer and is never shared.
  Maintainers: `blog_worker.generate` runs Claude Code with `--output-format stream-json
  --verbose` and Codex with `exec --json`, and reads their events as they arrive
  (`blog_worker.Events`, through `studio_core.agent_events`). Claude Code's answer is its
  last `result` event, or the one object an older CLI or a test fake prints; Codex's is
  still its `--output-last-message` file. The event stream may reach 32 MB while a
  result stays capped at 2 MB, and Codex's `error` and `turn.failed` events become its
  `ERROR:` lines, so connection failures are named as before. `blog_activity` keeps the
  running jobs on the engine (`Engine.activity`): `within` names the calls of a run stage
  or tool job, `labelled` a research phase or correction, and each call that ends is
  appended to `.blog-runs/activity/<blog-…|geo-report-…|workspace>.jsonl` under the studio
  lock, best effort. `.blog-runs` is Git-ignored in every workspace, so the log is never
  committed, shared or a team conflict. Views of a run, the desk, a GEO report, a
  find-text job and angles carry `activity`; `GET /api/activity` serves a log
  (`id`/`report`/neither), one entry's lines (`entry`) or a running job's lines
  (`job`, `since`). `os.killpg` treats macOS's `PermissionError` for an exited group as
  gone. The shared `describe` names Claude Code's `StructuredOutput` tool.

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

- **Research sources are kept as tidy text (#295).** Training Studio and
  Presentation Studio research stopped after synthesis with "capture differs from the
  accepted asset inventory" when a source had double or trailing spaces or several
  blank lines, because the source was registered as it came while the assistant read
  a tidied copy. Every studio now registers and gives the assistant the same tidied
  text: one space between words, no trailing spaces and at most one blank line. In
  Blog Studio, new research reads its sources that way; research that already kept
  checked work from the text as it came keeps it, so nothing is redone.
  Maintainers: `research_session.Workflow.asset` registers and offers
  `capture_text(text, kept)`, which is `shared_runner.worker_tools.tidy(text)` unless
  that source's own kept copies (`kept_copies`, at
  `sources/collection/<area>/<attempt>/<capture file>`) hold only the untidied text.
  Intake, the input fingerprint, the research basis and capture file names still come
  from the text as it came.

## 4.10.0 — 2026-11-03

- **Released with Marketing Studio 4.6.0.** Installs pin Harness Research 1.1.0 and
  Harness Slides 0.16.0; the brand skill needs 0.14.0 or newer and was tested with
  Tanzu Brand 0.14.1. Blog Studio 4.10.0; guidance needs runtime 4.10.0. This section
  covers every change since 4.7.0. The 4.8.0, 4.9.0 and 4.9.1 version numbers were set
  on the way and never published on their own.

- **Finding a post's text takes a second look when the fields are empty (#285).** A page's
  scripts often build the address of its article without naming the fields in what comes
  back, so Codex or Claude Code could find the right address and still guess the fields
  wrong, and the search failed with "held no text". Now Blog Studio gives the assistant
  one second look within the same 3 minutes: a bounded outline of that response (each
  field's pointer, type and first characters, a list's first items), shared fairly so a
  site's menus never crowd out the post, and nothing from the page's scripts. The assistant names only where the text, section headings and title
  are; the address stays as checked. The post is read in the response's order, section
  by section, with its headings as `##` headings, and goes through every check as before.
  Only the recipe that worked is kept for the site. Maintainers: `content_address`
  splits `apply` into `response` and `article`, adds `second_look`, `outline`,
  `pointers` and the `Empty` refusal, and orders fields with `_ordered`; recipes gain an
  optional `headings` list (`blog_worker.CONTENT_ADDRESS_SCHEMA`), and the second look
  uses `blog_worker.CONTENT_POINTERS_SCHEMA` (`response_kind` `content-pointers`).
  `tests/fake_site.py` adds a module-list response and a stand-in assistant.

- **A published post built by scripts can be read (#283).** Some blogs send an empty page
  and fetch the article with scripts, which Blog Studio never runs, so reading the link
  found no text. Now that message offers **Ask Codex to find the post’s text** (or Claude
  Code, as chosen under Settings → Writing preferences), on Link to a published post, the
  GEO report's start and Run again. It runs only on that press, takes a minute or two and
  can be stopped. Blog Studio gives the assistant the page's head and bounded excerpts of
  the scripts it loads from the same host; the assistant has no tools or web access and
  returns a recipe, never the article's words: an address on the same host, fixed query
  values, and where the article is in the response; an address that does not name the
  post is refused. Blog Studio reads that address itself (https only, the post's exact
  host on every redirect, no credentials or port, allowed by robots.txt, within 2 MB,
  asking for JSON where the recipe says JSON), turns it into Markdown as it reads any
  page, and uses it only when it is tied to the page: by its title, or by the page's
  description in the object the article's fields belong to (a listing of several posts
  never ties). The read then stages and is limited exactly like any other, and its
  preview says quietly that it came from the site's content address.
  A recipe that works is kept for that host on this computer, so the next post there is
  read straight away with no assistant; when one stops working, the offer returns and a
  new recipe replaces it. Maintainers: `content_address` (evidence, the recipe check, the
  address check and read, the per-computer store in Blog Studio's data folder), the
  `find-text` tool job, `blog_worker.CONTENT_ADDRESS_SCHEMA`, `published_post.NoText` and
  `robots_rules`, and the `published-find-text` routes. Tests use a local fake of such a
  site and stand-in assistants only.

- **The GEO review checks more of what makes a passage reliable to reuse (#280).** On the
  desk and in a GEO report, it now points out a claim missing the date, version, unit,
  region or audience needed to read it (and a measurement missing its method or sample),
  what the author observed against what others found, the conditions and tradeoffs after
  a direct answer, procedures that want numbered steps, charts and video whose point is
  not in the text, old product names with no word on the current one, and, where it
  matters, pricing, version or setup facts with no "as of" date. Decision support (who an
  option suits, its limits, a next step) is suggested only where it fits. Each change is a
  located proposal to preview, then apply or skip. A vague heading, which a change cannot
  edit, is named with a clearer one in the review's advice, and so is any detail only the
  author can supply (a date, a current name, what a chart or video shows): it is asked
  for, never invented, and a date is never refreshed without a change of facts. The FAQ,
  key takeaways and the other additions are described as aids for readers: none is said
  to earn citations or rankings. Finishing's group of them is now **Reader aids and AI
  search** (it was Improve discovery), and Tools' **Improve clarity for readers and AI
  search** replaces the older citation readiness wording. Maintainers:
  `blog-geo-review.md` (with its primary sources) and `manuscript_editor.CHECKS['geo']`.

- **A GEO report for a published post (#277).** **Get a GEO report for a published post**,
  on Home and in New blog, takes a link, shows the page read only, and starts one job on
  one press. The report is a typeset reading document: what already works, the changes
  ranked by how much they help (no score), the post with changes marked inline and a short
  reason beside each, additions shown where they would go, the questions it answers, the
  sources it needs, and **Page access** (noindex, a sign-in, robots.txt for Googlebot,
  OAI-SearchBot and PerplexityBot with GPTBot said apart, JSON-LD against the visible title,
  author and dates, and a byline and date), said as eligibility checks, never ranking
  promises. Download it as one self-contained HTML file that prints to PDF, or Markdown;
  make a new Google Doc with each change a suggestion and its reason a comment; **Edit this
  post on the desk** with the recommendations in Finishing; or **Run again**, which says
  what changed since. Reports are listed in Blogs as GEO reports. Maintainers: `geo_report`
  (reusing `desk_finish`'s readers), the `geo-report-*` routes, the `geo-report` tool job,
  `published_post.access` and `robots_check`, and `tests/fake_site.py`, a local fake site
  for link reads. A page is read in bounded time and space whatever its shape (open
  elements, list and quotation depth, a table's size, a byline's words and the Markdown made
  are capped as it is read), its words are kept as written with only what could become a
  tag, a link or an image escaped, and robots.txt is read as RFC 9309 says
  (`published_post.robots_groups` and `robots_allowed`: the most specific product token, the
  longest match with Allow winning a tie, `*` and `$`, percent-escapes of unreserved
  characters decoded, a byte order mark ignored), the same on every Python, not with
  `urllib.robotparser`. Page access says what it did not find as such,
  reads written dates, header bylines and "By" lines, compares an updated date only when the
  page shows one, and takes an X-Robots-Tag's crawler name into account. The Markdown
  download holds no HTML and no link but http(s). The report's Google Doc is placed with no
  lock held, and no page is read before write access is checked.
- **Review an existing or published post for AI search (#277).** New blog's polishing
  screen has a first pass, **Review for AI search (GEO)**, for a pasted, uploaded or Google
  Doc draft: the post's one GEO review starts as the desk opens and its proposals wait in
  Finishing, opened at it. **Link to a published post** is a new draft source: the page is
  read once on your press through the bounded fetcher, shown before anything starts, and
  refused plainly behind a sign-in, as another type or when too large; the desk works on a
  copy and the record keeps the link. A post in an Import old blogs collection has **Review
  for AI search**, which brings a copy to the desk the same way and leaves the collection's
  entry as it was. Maintainers: `published_post` (an `html.parser` article reader,
  `stage`/`staged`, `from_library`), the `published-preview` route, `desk.create`'s
  `published` field, `desk_jobs.geo_first`, and `blog_library.fetch`'s optional `limit` and
  `headers`.

- **GEO additions on request, and a GEO review for each post that asks for one (#276).**
  Finishing's **Reader aids and AI search** group adds an FAQ, key takeaways, a comparison table,
  quotes from sources, image alt text, likely search questions and a definition-style
  opening, each a proposal previewed, then applied or skipped. An FAQ (3 to 6 questions)
  and key takeaways are sections you place, choosing and editing each question or point
  and adding all or the ticked ones; on a post that has one, they propose its new form.
  Quotations are checked word for word against the source, alt text says it comes from
  what the post says because Blog Studio cannot see images, and search questions are
  advice only. New blog has **Include a GEO review**, off by default and changeable under
  the group on the desk: when it is on, one GEO review runs once the full draft is written
  and its proposals wait in Finishing. Before publishing shows the review done, waiting,
  under way or out of date, with **Run GEO review** beside the pre-publish check on every
  post. Existing posts start with it off. Maintainers: `desk_finish.ADDITIONS` and
  `ADDITION_READERS`, an inserted section applied by `_insert`, `desk_jobs.geo_due`,
  `geo_option` and `geo_view`, the post's choice in its record as `geo_review`, and two
  opt-in hooks in `ui-kit/drafting.js` (`groupAfter` and a tool's `status`).

- **Repurpose writes an SEO meta description (#275).** Repurpose, on the desk and in the
  older Tools path, offers **SEO meta description**: one line of up to 155 characters from
  the post's own claims, in its voice. Its length is counted in characters as you edit it,
  and anything longer is refused with a plain message; the word target does not apply.
  **Keep with this post** keeps it in the blog's record, never as a new blog, ready to copy,
  and it says the description may be out of date once the post changes. Maintainers:
  `article_tools.keep_meta`, `meta_view` and the `desk-meta` route; Copy and Download
  write no front matter, so export is unchanged.
- **A step says when the assistant cannot reach its service from this network (#274).**
  A step whose assistant could not connect no longer sends you to check sign-in and usage.
  It says, for example, "Codex could not reach OpenAI from this network", says when the
  connection is being intercepted, and suggests another network or the other assistant for
  new work under **Settings → Writing preferences**. A connection that failed or kept
  dropping says the assistant lost its connection and to try again in a moment, unless a look at
  this network confirms it is the network. **Status → Check this computer** now reports an
  assistant that is signed in but cannot be used from this network; setup's checks still
  never use the network. A connection that dropped and came back changes nothing.
  Maintainers: the TLS look moved from the shared runner's `agents` to
  `studio_core.reachability` (`blocked`, `reachable`, `codex_host`, `error_lines`,
  `connection_failure`), which `agents.ready()`, `blog_worker` and `computer` share. Each
  look keeps to one time limit, address lookup included, and a service that does not answer
  within it cannot be reached. `computer.report(network=True)` asks for the look. `WorkerFailure.reason` stays `cli` and `said` keeps the same lines; a Claude Code
  run that exits with an error result now keeps that result in `said` too.

- **Bring accepted changes reads a rewritten paragraph as it was sent (#267).** A
  paragraph rewritten outright, the opening's first paragraph included, or a paragraph
  added, goes to the Doc as a deletion with the new words on the paragraph beside it.
  Bring accepted changes now reads the two together, and reads a rewrite beside an edit to
  the next paragraph as one change. When the owner rejects such a change, the Doc's words
  come back, as they do for any other rejected change. When the owner accepted it, all of it
  or only a part, and the desk changed it back, the part is refused. When the desk changed it
  again, the desk keeps its words. A check that brings nothing back names the parts that
  still read differently on the desk and in the Doc, and says why: desk changes not sent
  yet, changes that went as comments for the owner to make by hand, or suggestions the
  owner did not accept. It no longer says the two agree. Maintainers: `_pull` in
  `desk_finish` reads each changed paragraph alone, with a neighbour whose carried lines
  reach into it, and with the changed paragraphs next to it, and returns `differs`;
  `_unsent_kinds` says how the desk's changes went.

- **One library vocabulary, honest upload limits and clear source choices (#260).** The
  page says **team library** and **Document Library (this computer)** everywhere: **From
  the team library**, **From the Document Library (this computer)**, **Keep a copy in the
  Document Library** for uploads, and **Add to the team library**. Mark as published names
  both places its draft is kept, and without a Team Hub the page says the team library is
  on this computer only. **Add to the team library** sends large files in groups that each
  fit one request, through the phone link too, and reads them back as one check and one
  result. **Add a source**'s five options wrap with exactly one shown as chosen. Team
  library rows show one status in words ("Readable · not analyzed yet"), the Status filter
  reads **All active**, and its dialogs close with **Close**. Opened through Marketing
  Studio's phone link, Status says to run sign-in commands on the computer running
  Marketing Studio. The desk's **Add a source** says "Later rewrites will read what you
  add." On a phone the desk's save line sits in its compact bar. Shared look: a `.dialog`
  that holds form fields is opaque, and a five- or six-option segmented control fills the
  chosen option instead of sliding a thumb.

- **The Google Doc round trip, finished on the page (#259).** The desk's **Google Doc**
  is a small menu: **Open the Google Doc**, **Check what would be sent** (then **Send**) and
  **Bring accepted changes**. Bring accepted changes reads the Doc's accepted text and
  lists each part it changes, merged paragraph by paragraph against the Doc as the desk
  and the Doc last agreed: what only the Doc changed comes, a suggestion the owner rejected
  comes back (matched by its paragraph, never its words alone), and every desk paragraph the Doc has not answered (unsent, or sent as a
  comment for the owner to make by hand) stays. Each part taken keeps the desk's text in
  History as "Before Google's accepted text", and the Doc becomes the new baseline. The
  desk's section order, and the sections it added or removed, are kept. A paragraph both
  changed refuses its part, as does an image the desk holds differently, and the whole
  check waits while desk suggestions are still with the owner. Nothing is written to Google, and a slow answer through the
  phone link says to check again. The send
  receipt says what went and when, and the desk, Home and Blogs say what waits in the Doc,
  when the desk last sent, and when it has unsent changes; Home counts a desk blog with
  open suggestions, Doc suggestions waiting or unsent changes as needing you, and each row
  has one status line with when it was edited. What a send makes reads plainly ("Removes
  …", "Adds a paragraph after …"), and the Doc's pending marks are counted and explained in
  Review mode before a first check too. Maintainers: `desk-google-compare` and
  `desk-google-take` (`desk_finish.google_pull`, `google_take`), `google_state` in the desk
  view and `needs` in the runs listing (`desk_finish.attention`); the desk's Google ledger
  keeps `last`, `waiting`, `synced` and `brought`.

- **The manuscript in its order, and one path through Polish and Review (#258).** Read,
  Edit section, Full desk and Review mode always show the title, the opening, then the
  sections as saved: a section whose id was all digits could show above the title.
  **Polish** opens Review mode and **Back** there returns to the view, section and scroll
  you came from; Review mode keeps **Copy**, **Download**, the **Google Doc** and **Mark as
  published**, and shows **Check again** only once a check has run, with a first-run
  sentence before it. The desk's **Review and share** button is gone: the toolbar's
  **Finishing** is the one way to the panel. After **Accept**, **Reject** or **Accept all**
  focus moves to the next suggestion or the summary; **Reject** is said, with **Undo**.
  **Humanize · N to review** opens Review mode with the rewrites to accept or reject; in
  Finishing, waiting rewrites come first and **Find sentences again** is quiet, under them,
  saying it replaces them. On a phone, Go to section and one **View and tools** fold come
  before the text. Maintainers: the `desk-unskip` route (`desk_finish.unskip`), and Review
  mode's `reviewFrom`, `reviewHuman` and `focusAfter`. Presentation Studio and Training
  Studio list their parts from arrays, so their desks were not affected.

- **Document Library: Update available and Keep in library.** A desk source taken
  from the shared Document Library shows **Update available** when the library has
  a newer revision, and **Use revision N** takes it as a new source revision the blog
  pins; nothing changes until then, and it waits while a desk job runs. Uploading
  files offers **Keep in library** (the default) or **Only this blog**; a kept copy is
  local and never changes the file's sharing. Maintainers: `shared_library.marked`,
  `update` and `keep_upload`, the `desk-library-update` route, and the upload field
  `document_library`. Marketing Studio's **Add existing work to library** reads this
  studio's team library without changing it.

- **Polish the blog without its approval form.** Google dropdowns read as their
  selected text. New manuscript imports leave clearly labelled leading approver
  and reviewer chip fields out of the editing copy and explain this in the
  preview. Their original Google content and coordinates are preserved; suggestions
  and comment fallback stay within the manuscript. Ambiguous fields, bylines and
  dropdowns in the article remain visible. Reference intake retains all content,
  and older linked blogs retain their original capture scope.

- **Preview opening eligible unfinished blogs on the writing desk.** Supported
  manuscripts and lossless heading-based outlines open only after explicit preview
  and guarded apply. Original session/run records, decisions, source pins, History
  and Google baselines remain in place, including after checked desk edits. Missing
  materials and early research/angles retain their saved flow. Interrupted apply
  excludes workers and sharing until the original command safely recovers it.
  Blog Studio and guidance now require runtime 4.9.0.

- **Work on the desk directly in conversation.** Checked create, show, save, context
  and submit commands keep the requested scope and never start another assistant.
  A version-checked handoff explicitly transfers requested remaining steps. New desk
  work pins saved author and brand choices while retaining tone-only writing.
  Proofread also finds editorial notes, source IDs and example carry-over; Finishing
  offers GEO proposals to preview and apply. New `run create` requests point to the
  desk commands; saved step-by-step work remains available. Blog Studio and guidance
  introduced these commands in runtime 4.8.0.

- **A Google Doc with large images reads, its large images kept in the Doc.** Reading a Doc
  whose images came to more than a blog's shared files hold stopped with "This Doc, with its
  images, comes to more than a blog keeps (1 MiB)". Now its images come in, in document
  order, while their data fits about 600 KiB; one too large for the room left stays in the Google Doc and
  shows on the desk as "Image kept in the Google Doc", with one line saying how many. This
  holds for a Doc read with or without pending suggestions; a kept image is never seen as
  changed on a send or a later read, and Copy and Download leave it out. For maintainers:
  `google_suggestions.fit_images` (and `IMAGE_ROOM`, `KEPT_ALT`, `kept_like` for the
  snapshot check), applied in `google_roundtrip.capture` to both projections;
  `desk_images.kept_in_doc` and the desk view's `kept_images`.
- **A date chip in a Google Doc reads as its date.** A Doc with pending suggestions and a
  date chip stopped at "This Google Doc holds something (dateElement)". The date now reads
  as Google shows it, and a newer kind of chip reads by the text it shows instead of
  stopping the read. Maintainers: `google_roundtrip.chip_text` is the one place a chip's
  words come from, for the read, the pending-suggestion record and the send.
- **A Google Doc with other people's pending suggestions reads like a clean one.** Reading a
  Doc whose suggestions were still waiting stopped at "Review pull cannot project embedded
  objects", and **Read Google Doc** looked stuck after it. Now the Doc reads as it is
  without the suggestions, with its images and their data (as Google's export writes them),
  smart chips, line breaks, footnotes and tables; page breaks, headers and footers are left
  out. An image Google does not send stays a visible placeholder, and anything else is named
  plainly, and the text is the very Markdown Google's export writes (links, lists, image
  data), so a later read either way sees no change Google did not make. Reading again
  after a failure says so as a new answer. On such a Doc a desk change beside an image, a
  chip or someone else's suggestion goes as a suggestion placed by the Doc's own indexes;
  only words their suggestion changes go as a comment, and a teammate's suggestion holds
  nothing. For
  maintainers: `google_suggestions.accepted_markdown(value, images=…)` reads every object
  (projection `blog-studio-objects/1`, re-read from the snapshot with the image data it
  kept), `google_drive.Client.image` fetches an image's `contentUri` from Google's image host
  without a token, a comment may now sit on plain words of a paragraph with objects or
  someone else's suggestion, and `tests/google_model.py` has `objects_doc()` and
  `teammate()`.
- **Other people's pending Doc suggestions are shown on the desk.** When a Doc is read, its
  pending suggestions are recorded beside the blog (on this computer) and marked in Review
  mode and on the full desk as **Suggested in the Doc**, with no Accept or Reject and never
  counted with our fixes; Review mode says how many are pending. Copy edit and Humanize are
  told what the Doc suggests, a fix over the same words is flagged as making it moot and
  left out of Accept all, and the Google send plan says how many changes are over a Doc
  suggestion's words (they go as comments). For maintainers: `google_pending.record`,
  `keep`, `read` and `on_desk`; the desk view's `doc_suggestions` `{count, marks}`; review
  payloads carry `doc_suggestions` with `DOC_PENDING` guidance; the plan returns
  `doc_overlap`.
- **Review suggestions stay independent.** Accepting a fix no longer throws away a
  Humanize rewrite of the same sentence, nor the other way round, and never leaves one that
  would undo it. Each suggestion is read by the words it actually changes. One whose own
  change the accepted one left as it was stays, shrunk to that change and a little context
  and marked in place: a fix "Agentic AI" → "agentic AI" stays after a rewrite that kept
  "Agentic AI". A rewrite of the whole sentence takes a fix in where it kept the fixed
  words ("Here, Agentic AI has arrived." becomes "Here, agentic AI has arrived."). One
  whose own words the accepted one changed says "No longer fits: its words were changed
  by suggestion #N", as does one that adds words where the accepted one added its own (so
  "the" is never added twice); suggestions keep their numbers while you review, and later
  ones are numbered after them. A cut beside a changed word keeps the new word as context
  ("really use" → "use"), and no double space is left. Alternatives follow the same
  rule. Human-sounding suggestions that arrive after fixes were accepted are kept
  in step the same way instead of being dropped, and one for words edited by hand
  meanwhile says so. **Accept all** applies what is shown and not flagged, from both
  tools, in reading order, each against the text the ones before it left; it no longer
  leaves out a rewrite over a waiting fix. A flagged or hidden suggestion stays unless its
  words were changed, and Accept all leaves a suggestion that would retire a flagged one or
  a fix **Show** hides. Its message counts what was accepted, updated to fit, no longer fits
  and left for you. For maintainers: `desk_finish.apply` no longer retires by overlap (`_retire`,
  `_flagged_spans`, `_covers` and the `OVERLAP` refusal are gone). Picks land one by one in
  reading order (`_reading`: part, start, Copy edit first, shorter first). After each,
  `_reconcile` checks every other open item from the waiting Copy edit and Humanize sets.
  `_word_edits` aligns words to find what a text change, or an item's own wording, changes.
  Both the accepted change and an item's own wordings are aligned against the whole part
  (`ALIGN` characters of context), as a three-way merge would. An item the accepted change
  touched, or added words at its edge, retires when the two meet, including two insertions
  at one place. Otherwise its own changes move onto the new text: it keeps its sentence
  when the change sits among them, else it shrinks to its own change with up to `CONTEXT`
  words of context from the new text and its marks, found once as whole words (`_windows`).
  A wording left empty retires the item, a cut no longer leaves a double space, and a flag
  is read again but never dropped. With `all: true`, a pick that would retire an unsent
  flagged item or an unsent Copy edit item is left out (`_would_retire`, `WAITING`).
  Applied items record the wording that `landed`, which `_owner` matches. Each word alignment is
  kept for the texts it read (`_aligned_words`), a suggestion no accepted edit comes near is
  not aligned at all (`_near`), and a waiting one is tried only when the change reaches it
  (`_reaches`), so Accept all over 120 suggestions in a 5,000-character part takes under a
  second while it holds the studio lock.
  A retired item gets `reason` and `retired_by: {job, id}`; an updated one records
  `carried: [{job, id}]`; all stay in the ignored proposal sets. `settle` reads a Humanize
  result against the text its job read (`_earlier`) and reconciles rows for words changed
  since, naming the accepted fix (`_accepted`, `_owner`) or `EDITED`. `desk-apply` items may
  name another waiting sentence set with `job`; `all: true` leaves out a flagged pick; and
  `finished` adds `carried` and `retired` counts when there are any. Review mode sends
  Accept all as one request, keeps each suggestion's number while its set is shown and numbers a later set after them (`numbers`), and shows
  `carriedBy` and `byNumber`.
- **Every desk change goes to the Google Doc.** **Send accepted changes to Google Doc** and
  **Send to Google Doc** no longer leave changed paragraphs on the desk. Each separate
  change in a paragraph is its own suggestion, so only the changed words are struck
  through, also beside or inside a link's text. A paragraph added is a suggested insertion
  after the one before it, one removed a suggested deletion with its break, and a split a
  suggested line break. A link's new address, bold or italic, a heading level, an image or
  a table row is a comment on its words or the closest paragraph, and a change the Doc
  could place with any doubt is a comment on the closest certain paragraph, quoting it
  before and after. The desk's title line is no longer counted as a change when it is the
  Doc's name; a different title is a comment. The plan says "N suggestions and M comments
  go to the Google Doc" (or that they go as comments, when Google cannot take
  suggestions), and a change in a paragraph still waiting on an earlier suggestion goes
  next time; while one of the blog's own suggestions, edited again since, still waits in
  the Doc, nothing is sent. Inserted words come in with the desk's bold, italic, underline
  and links. A note about a paragraph is a comment of its own, and one with no free
  paragraph nearby goes with the next send. For maintainers: a finding may carry `styles`
  (`[[length, {bold, italic, underline, link}]]` over its replacement), and
  `desk_finish.google_changes(baseline, body, title)` diffs each paired paragraph's shown
  text word by word (`_styled` reads each character's style from the Markdown) and returns
  edits, comments and `remove` edits;
  `desk-google-plan` reads the Doc first for its name and returns `suggestions`,
  `comments`, `waiting` and `left`, and `_not_pending` turns a proposal it cannot place
  into a comment on the closest paragraph the Doc shows once. In `google_suggestions`, an
  edit deletes and inserts only what differs from its quote at whole-word boundaries
  (`trimmed`), a replacement may hold line breaks, a finding may set `remove: true` to
  delete its whole paragraph with the break where the next block is a paragraph, a pure
  deletion may cross style boundaries, text is inserted only at a quote's end or very
  start, removing the last paragraph deletes the break before it, and a plan that splits
  or removes a paragraph is verified by every character and its style across the accepted
  view (`expected_text_sha256`), or by its paragraphs' text while other suggestions wait
  (`targets_show` reads on across a suggested break). `_not_pending` counts copies in each
  paragraph's text without pending insertions and places each change by index; the sent
  record keeps each row's baseline transfer and the Doc's name, and Google is not read
  when nothing changed. `tests/google_model.py` models Google's suggest mode more closely.
- **Every control is at least 44px tall,** and on a phone the selection bar sits above the
  tab bar. The library's filter row, selection bar, ticks, research choice and sheet steps
  now take their styles from the shared stylesheet; nothing else a person sees changes.
- **Human-sounding suggestions, mixed into Check spelling and grammar.** Under **Check
  spelling and grammar**, tick **Also suggest more human-sounding wording** and choose
  **Light**, **Medium** or **Strong**: Humanize runs after Copy edit ("Looking for
  machine-like wording…", with **Stop** for both), and Copy edit's fixes can be accepted
  meanwhile. In Review mode every suggestion is labelled **Spelling**, **Grammar**,
  **Punctuation**, **Consistency**, **Wording** or **Sounds human**, both tools read together in order
  under one count, and **Show: All · Fixes · Sounds human** narrows them. A wording fix may
  offer up to three alternatives to pick from before **Accept**, and **Accept all** still
  leaves flagged ones from both (see **Review suggestions stay independent** above).
  Quick check's findings are listed at the top with **Fix** and **Dismiss**, and **Check
  again** reruns both. A save that finds sections reordered elsewhere now shows the new
  order. For maintainers: `desk-create` takes `humanize: "light" | "medium" | "strong" |
  null` with `first_pass: "copyedit"` (part of the start's fingerprint when set); the new
  `desk-review` route (`{id, seen, humanize?}`) queues `finish-copyedit` with
  `metadata.desk.review` and `then`, and `finish-humanize` is queued once it settles or
  fails, once, unless Stop ended the check. The strength is pinned in the ignored
  `.blog-runs/desk-proposals/<blog>/review.json`, so a team tree stays clean; the desk view
  carries `review: {humanize, problem}`. Copy edit items carry `kind` (spelling, grammar,
  punctuation, consistency or wording, else grammar) and, for wording, up to three
  `alternatives` `[{after, flag}]`; `desk-apply` takes `{id, alternative}` items and
  `all: true` for Accept all, and leaves out a pick already retired. A Copy
  edit that fails at model routing or is interrupted (`tool_jobs.recover`) still queues its
  Humanize, once.
- **Workflow fixes on the writing desk.** A teammate can take over a desk blog (**Take
  over**, **Take this blog**, **Hand over**), and the desk is read-only while someone else
  drives it. A stopped start offers **Try again with more time**, **Continue without
  research** and **Open Status** with what the assistant said, beside Retry. A restored
  desk blog opens on the desk. **Make a Google Doc** gives a desk blog its Google Doc.
  **Mark as published** keeps the draft in the team library. The library upload's **Then
  edit it on the desk** opens the draft screen, the paste field takes up to 200,000
  characters, and the stepped start asks what you have before sources and settings. Page
  words name each thing once.
- **Check spelling and grammar, reviewed in your text.** Polishing a draft now starts
  with **Check spelling and grammar**: Copy edit runs and the blog opens in **Review
  mode**, where the draft reads as a document, section by section, with each fix marked in
  place (struck words out, highlighted words in), its reason, and **Accept** or **Reject**.
  **Accept all** leaves a fix that changes a fact, code or shape for you to check, and
  **Reject all** sets every fix aside. Click any paragraph to edit it in place; the other
  fixes stay, and one whose words are gone drops out. **Check again** reruns the check.
  When nothing is left, a blog from a Google Doc sends only the accepted changes as
  suggestions (the plan says how many first); others offer Copy and Download. **Open the
  full desk** has notes, the outline and Finishing, where **Copy edit** now opens Review
  mode too. The Google send says it sends every difference from the Doc as it was read:
  accepted fixes and your own edits, never rejected ones. The silent **Proofread and
  tighten** is gone from the polishing screen. **Headings at any level start sections**: a Google
  Doc's `### **Bold**` headings no longer leave the whole draft as one opening, and blogs
  already on the desk that way are divided into their sections when next opened, with no
  word changed; a page left open on the opening is asked to reload, and restoring the
  opening from before the division (such as before a silent first pass) brings its
  sections back. Indented headings and a tab after the marks count, and a draft of more
  than 60 sections is refused readably. Typing in the **Note for the whole draft**, or any
  desk field, no longer loses focus while a job works or adds a section, and a field
  focused while its own section was rewritten now shows the rewrite, so a keystroke can no
  longer save the old text over it. For maintainers: `desk-create` takes `first_pass:
  "copyedit"`, which queues `finish-copyedit` as `"feedback"` queues `finish-feedback`
  (`tighten` stays for chat and older callers); `desk.split` divides at the shallowest
  heading level from `##` to `######` below the title, keeps a section's `level` when it is
  not 2 and its heading as written, and `join` writes it back; parts are checked against
  `desk.limit(draft)` (2 for a record still undivided); `desk.read` divides an
  opening-only record once, under the lock on the driving computer, one revision on with
  `opening` and `outline` marked changed, committed with `keep_desk` in a team workspace and
  pushed with the next decision. Review mode is the desk page with `stage=review`.
- **Copy edit in Finishing, with each fix approved first.** **Finishing → Copy edit**
  finds grammar, spelling, punctuation, consistency, clarity and concision fixes in the
  title and the text and shows each one before and after with a note on why, to
  **Apply**, **Edit** or **Skip**, or **Apply all**; a fix that changes a fact, code or the
  part's shape is flagged and left out of Apply all. Claims, qualifiers, the argument,
  voice, quotes, links and image references are kept. Finishing's mechanical
  **Proofread** is now **Quick check**, so it is not mistaken for the grammar pass. The
  panel's tools are now in this order: **Copy edit**, **Humanize**, **Quick check**,
  **Check facts against sources**, **Headline and opening**, **Feedback without a
  rewrite**, **Apply a voice** and **Before publishing**. The polishing screen says how to
  approve each fix first: **Leave it as it is**, then Copy edit. A suggestion whose only
  change is to an image reference says there is nothing to apply instead of reporting it
  applied, text that occurs twice, overlapping, is no longer taken as one place, and a
  word after an image reference is no longer flagged as a changed name. For maintainers:
  the `finish-copyedit` job (`desk-finish` with `tool: "copyedit"`) sends the draft and
  its tone only (no sources, examples or kind of post), with
  `desk_jobs.desk_check('copyedit')` and `('proofread')` (the manuscript editor's checks
  without pinned author rules, which the first pass's tighten now reads too) and only the
  clarity and voice lenses of `references/modules/copy-editing.md`; its result is read
  like `finish-humanize`, with `title` also accepted. Quick check keeps the `proofread`
  key and `GET /api/desk-proofread`.
- **Images stay out of the desk's text.** A draft with images, such as a Google Doc's,
  now shows each one in its part as the short reference `![][image1]` with a thumbnail
  under it, instead of a wall of base64. The images are kept beside the draft and written
  back at the end of `DRAFT.md`, so Copy, Download, the Google Doc send, the team library
  and the pre-publish check keep them exactly, and no rewrite, note, selection edit, first
  pass, Finishing tool or voice sends them to the assistant. A rewrite that drops a
  reference has it put back where it was. Blogs already on the desk are cleaned the first
  time they are opened, and an image an earlier rewrite dropped is found again in History,
  the original draft or the Google Doc, with no word changed; one found nowhere shows
  **Image missing**. Image data kept as text, such as in a code example, reaches a rewrite
  as a token it must give back unchanged. For maintainers: `desk/draft.json` lists `images` ({label: {alt, key,
  size}}) and their data is in `desk/images.json` ({label: data URI}), read only to write
  `DRAFT.md` or by `GET /api/desk-images`, never on a view poll; `desk_images.py` moves
  them in and out; the view's `missing_images` names labels kept nowhere; part limits count
  text only, with images capped at 5 MB each and 12 MB in all; the page's `img-src` allows
  `data:`.
- **Polish a draft without choosing a kind of post.** **Edit or polish a draft**, **Polish
  another document**, a saved blog's draft and **A draft** on the start open one screen
  with no step tabs: your draft, then **Proofread and tighten** (the default), **Just give
  feedback** (Finishing's feedback as the desk opens, with nothing rewritten), **Reshape
  to fit a kind of post** (the only choice that asks for a kind) or **Leave it as it is**,
  with optional tone and sources for the fact check. For maintainers: `desk-create` takes
  `first_pass: "feedback"`, which queues the `finish-feedback` job once the blog is made.
- **Proofread a draft with no headings.** The first pass, and a note for the whole draft,
  now work on plain prose with no `##` headings as one part, and the first pass covers the
  opening too. Proofreading adds no headings; only **Reshape** may divide such a draft into
  sections, and restoring the opening from before it undoes the division as a whole. A
  first pass is refused only for a draft with no text.
- **The writing desk.** New blogs are made on one editing desk, with no stops along the
  way.
  - **Three ways in.** **New blog** asks what you are writing (a kind of post), takes
    your sources and settings (files, links, Google Docs and team library posts, each
    facts, approved messaging or an example; **Search my sites** and **Search the web
    too**, ticked as Settings' research for new blogs says and changeable per blog; length
    and tone), then what you have: **Just a topic** (with
    **Suggest three angles** if you like), **An outline or notes** (write from it, or
    shape it with you first), or **A draft** (pasted, uploaded or a Google Doc, with an
    optional first pass). Sources stay with the blog unless you tick **Keep in the team
    library**. After **Start** the page says "Nothing needed from you" and opens the draft
    on the desk when it is ready. An interview's outline and a saved blog's **Open writing
    run** start here too.
  - **The desk.** The draft is one page: the title, the opening and a card per section,
    saved as you type. A note under a section rewrites only what it asks for; **Write
    again** writes it fresh; a note for the whole draft revises every section in turn.
    Select text to rephrase, shorten, expand, fix or ask for a change. **History** keeps
    the last twenty versions of each part, with a comparison and **Restore**. The
    **Outline** tab renames, reorders, adds and removes sections and writes from them.
    **Add a source** takes more at any time, and anything the writer could not settle is
    listed under **Needs you before publishing**, never in the prose.
  - **Finishing.** A side panel of tools that propose and change nothing until you apply:
    **Humanize** (light, medium, strong), **Proofread**, **Check facts against sources**,
    **Headline and opening**, **Feedback without a rewrite**, **Apply a voice** and
    **Before publishing** (the pre-publish check, **Repurpose** into a new blog, and **Send
    to Google Doc** as suggestions). Each change shows before and after with **Apply**,
    **Edit** and **Skip**, or **Apply all**; a change that would alter a fact, code or a
    part's shape is flagged and left for you. Each Apply keeps the earlier text in History.
  - **Voice guides.** **Voice guides** replaces Voices in the sidebar: a name and a page of
    text, written by hand or made from 3 to 20 samples, then read and edited before saving.
    Voices learned before are listed as guides. **Kinds of post** has its own screen.
  - **The older voice tools are hidden for now.** Learning voices from samples, auditions,
    **Write as**, the default voice, **Change the voice**, voice samples, LinkedIn imports
    and **Create voices for every author** are off, behind **Settings → Advanced → Show the
    older voice tools**. New blogs write with their tone. Saved voices, samples and every
    blog's pinned voice are kept.
  - **Older blogs keep their path.** Blogs started step by step continue through outline,
    draft, review and handoff as before. A finished one opens at its Done card from Home and
    Blogs, and **Open on the desk** there or in the manuscript editor brings it onto the
    desk, with any edits made since in the editor. The old new-blog wizard and **New blog
    from my files** are gone from the page, and **Polish another document** starts on the
    desk; chat runs work as they did.
  - **Edits made elsewhere land on the desk.** A draft saved in chat, restored from its
    history or accepted from Google comes onto the desk as a new version of each part it
    changes, so the next desk save keeps it.
- **For maintainers: the writing desk.**
  - **The desk record.** `scripts/desk.py`: `desk/draft.json` and
    `desk/versions/<part>.jsonl`, with `DRAFT.md` kept in step; `desk.create` takes `way`
    (`draft`, `topic`, `outline`, `shape`) and `article` for a saved draft, with
    `desk/start.json` beside the draft; routes `POST /api/desk-<action>`, `GET /api/desk`
    and `GET /api/desk-versions`; `POST /api/desk-share` shares a desk's locally kept
    edits. A start's phase and problem stay on this computer (`.blog-runs/desk-starts/`),
    and a decision first commits desk leftovers under any blog this computer drives.
  - **Desk jobs.** `scripts/desk_jobs.py` on the tool queue: `desk-section`,
    `desk-revise-all`, `desk-selection`, `desk-first-pass`, `desk-angles` (before a blog
    exists, keyed by the page operation), `desk-research` (the research plan, then Harness
    Research or one web research job, with no gate), `desk-outline` and `desk-draft`, with
    `references/modules/desk-edit.md` and `desk-write.md`. The worker settles a result as
    soon as it is ready and records it as a team decision; reading the desk never writes.
    An `upload` entry may be a `link` read through the library's fetch; `desk-create` and
    `desk-sources` take `keep`, the sources the server moves to the team library once the
    blog is made. `blog_runner.shared_guidance`, `FROM_OUTLINE`, `WRITING_NOTES` and
    `GAPS_OPEN` name what runs already used, unchanged for runs.
  - **Finishing.** `scripts/desk_finish.py`: job kinds `finish-humanize`, `finish-facts`,
    `finish-headline`, `finish-feedback` and `finish-voice` (`desk-finish` with `guide`;
    the guide's text in the payload while `desk_jobs._context` stays tone-only) that write
    no part and return JSON read strictly; proposals wait in `.blog-runs/desk-proposals/`
    and Google sends in `.blog-runs/desk-google/`; routes `desk-finish`, `desk-apply`,
    `desk-skip`, `desk-repurpose`, `desk-google-plan`, `desk-google-send` and `GET
    /api/desk-proofread`; `desk_finish.changes_structure` flags changed code, blocks or
    shape; the editor's Google plan and send are `manuscript_editor.google_plan` and
    `google_send`.
  - **Voice guides and the switch.** `features.voice` in `.blog-run-settings.json`, read by
    `studio.features`, `voices_on` and `require_voices` and saved by `blog_runner.settings`
    with `features_before`; `management.old_voice_tool` refuses the older routes before
    anything is read; no default voice applies while off. Job kind `voice-guide`
    (`article_tools.guides`, `guide_samples`, `job-apply`, `GET /api/voice-guides`, indexed
    in `.blog-runs/voice-guides.json`, `guide-discard`). Tests turn the switch on with
    `isolation.voices_on(root)`.
  - **Team workspaces.** A start's research is returned with its job and staged in
    `.blog-runs/desk-starts/<id>/` until it settles, so nothing in the blog's folder is
    changed outside a decision while it works; Refresh, retry-sync, team-sync, the team
    actions and the background check keep desk leftovers first; `desk-share`
    (`team_workspace.share_desk`) pushes only this blog's unshared commits and never
    claims a driver. `desk.reimport` takes a chat save, a restore or Google's accepted
    text onto the desk (versions from `chat` or `google`). The run's `finished` and the
    list's `desk_open` let a finished blog edited in the editor go on the desk; a saved
    blog brought with `article` keeps a pinned voice. While voices are off, uploads as
    `author-background` and `GET /api/library-authors` are refused.
  - **The page.** `assets/management/desk.js` beside `runner.js`. The old wizard
    (`newBlog`, `sWizard`, the from-files screen, `sStartBlog`, the per-blog brand choice,
    Where this run stops and their research and stops helpers) is removed; `screen=new`
    opens the desk start. `sDeskResearchDefault` starts the desk's research ticks from
    `defaults.research`. The gates, the angles gate for older from-files runs, the
    manuscript editor and the server's `run-create` stay.
- **Select all in the Team library.** Tick **Select all on this page**, or, once anything
  is ticked, **Select all N matching** to tick every item the filters match. Ticks stay as
  you page and change the filters; the selection bar says how many are out of view. A
  selection holds up to 500 items. Learning a style or a voice reads twenty of them; a blog
  takes up to fifty.
- **Create voices for every author.** From the Team library, the Voices screen or the
  result of Add to library: every author in the library by exact name, case and spacing
  aside, with their post count, ticked when they have two readable posts (up to 100 in a
  batch); an existing voice of exactly that name is updated rather than duplicated. One
  permission for the batch; every author is checked before anything is marked or queued, so
  a refusal for one changes nothing. Then one learning job per author on the usual queue,
  each reviewed and confirmed as before. An author whose voice is still waiting or being
  learned keeps that one job: another batch shows it as Queued instead of starting a
  second learning. A learning from library items now checks the same before it marks any
  item as a sample.
- **Is "Dan" Dan Smith?** In Create voices for every author, a name whose words all appear
  in a fuller author name or voice ("Dan" in "Dan Smith" or "Dan Baskette") shows "Might be
  the same person as …", even when it is too small to learn alone. **Same person as Dan
  Smith**, once confirmed, names that author's posts Dan Smith, one reference at a time, so
  they count toward that voice; a list that changed since it was shown is refused.
  **Different person** is remembered for every suggested name at once, and the suggestion
  stops. Nothing is merged without
  the person's choice, and **Review details** now has an Author field, so any post's author
  can be corrected or changed back.
- **Create a voice** and **Create a style** replace Learn a voice from samples, Import a
  LinkedIn export, Add links to posts, Upload an authored sample, Learn a style from
  examples, Add links to examples and Upload an example. One sheet each, in order: the
  name, the writing from any source (links, uploads, a LinkedIn export, posts already in
  the library), up to twenty ticked samples, then build. Every source returns to the sheet.
- **Add to library** reads each post's own author by default, and offers **Import a blog
  or site** and **Upload one file** under **More ways to add** (they were the Team library's
  Import old blogs and Upload buttons).
- **Layout.** The library views (All blogs, Review findings, Team library, Team memory) use
  the shell's toolbar: one primary action each, **Library and team tools** (was Editorial
  tools) beside it, a one-sentence lede, one filter row with **More filters**, and on a
  phone a **Filters** button and the selection bar above the screens bar. **Refresh Hub**
  moved beside **Check access** and into Team sharing on Status and Settings. **Voices** is
  a screen with Create a voice and Create a style in its toolbar. Home lists what needs you
  and what is in progress before the ways to start; Blogs is titled Blogs and leads with
  New blog; Settings puts writing preferences first and has no back button.
- **For maintainers:** `GET /api/library-matching` (the catalog's filters, up to 500 ids),
  `GET /api/library-authors` (with `suggestions` and an `expected` version per author),
  `POST /api/library-voices`, `POST /api/library-author-same` and
  `POST /api/library-author-different` (pairs kept in `.library/author-pairs.json`) in
  `library_add.py`; `curate` takes `author`, recorded as a curation override;
  `library-selection` accepts up to 500 items for learning. The layout rules are in
  `docs/design/golden-gate.md`.
- **For maintainers: the desk's parts are shared.** Nothing changes for authors. The
  desk's text-keeping rules moved to the monorepo's `core/studio_core/drafting/` (with
  `text_checks.py` and `step_times.py` beside it), its page parts to `ui-kit/drafting.js`
  and its styles to `ui-kit/style.css`; `desk.py`, `desk_jobs.py`, `desk_finish.py` and
  `desk.js` keep every name they had and call them. `references/modules/desk-edit.md` is
  now `studio_core.drafting.prompts.edit_rule('blog draft')`, word for word, and
  `scripts/text_checks.py` keeps its command line over the shared checks. A desk job
  whose rewrite changes a number, a link, a quotation, a name, code or its part's shape
  still lands, and now keeps `checks: {part: what to check}`, which the desk view's job
  rows carry.

## 4.7.0 — 2026-10-23

- **Released with Marketing Studio 4.5.0.** Installs pin Harness Research 1.0.1 and
  Harness Slides 0.16.0; the brand skill needs 0.14.0 or newer and was tested with
  Tanzu Brand 0.14.1. Blog Studio 4.7.0; guidance needs runtime 4.7.0.
- **Research from your documents, your sites and/or the public web.** The start screens
  and the files screen read "Research from: your documents · your sites (3) · the public
  web", each a tick, in place of "Also research the public web" and the old research list.
  Your sites are the list in Marketing Studio's Shared settings, each with its own tick;
  **Add a site for this piece of work** checks an https address and uses it for this blog
  only, leaving the shared list as it is. The line under the choice names the sites
  ("Research from your documents and 2 of your sites (…)"), and a blog keeps the exact
  sites it started with. With your sites and not the public web, research saves a page only
  from under a listed site, redirects included; pages elsewhere become source limits that
  name the sites, and the research review and a refusal say how many were kept out.
  Discovery searches your sites first with `site:` queries. Settings → Writing
  preferences has the same three ticks for new blogs; none ticked is no research. Saved
  blogs and settings keep their meaning: supplied sources read as your documents, public
  research as your documents and the public web. Your sites stay unticked until you tick
  them, and the form says how they are searched: "Your sites are searched with the
  assistant's web search; only pages under them are saved." Research from your sites
  alone needs Harness Research, which does that check; without it the blog is not
  started, and Status says whether Harness Research is installed. No research job is
  given web search unless the public web is ticked.
- **For maintainers:** `run create --research-from documents,sites,web` and a repeatable
  `--site`, with `--research none|supplied-only|web-allowed` still read. A run saves
  `research_from` (`{"documents", "sites", "web"}`) on its record; `research_policy`
  is derived from it for saved runs and pins, and a run without it reads its policy
  through `studio_core.research_sites.legacy`. `blog_library.fetch` also takes a
  `research_sites.Scope`, asked about the first address and every redirect, raising
  `blog_library.Outside`; collection imports keep their string scope. The page checks a
  per-blog site with the new `research-site` route.
- **Voices and styles from Home and the sidebar.** Home has a "Set up before you write"
  card with Voices and styles and the Team library, and the sidebar has Voices, so
  learning a voice or a style no longer starts from a blog or from Tools.
- **Delete a blog from Home.** Each blog under **Needs you**, **In progress**, **Finished
  drafts** and **Saved drafts** has **Delete** beside its way in, with the same typed-title
  confirmation as its card on **Blogs**. Home is drawn again without it, and it is kept for
  30 days under **Recently deleted**.
- **Learning a voice or a style reads up to twenty samples**, up from ten, and up to
  800,000 characters of them in one job; a sample may be up to 200,000 characters. When
  the chosen samples are longer than one job takes, each long one is cut to a fair share
  at a paragraph and marked, and short ones are read whole.
- **Voices and styles lists a long style name as a line**, beside a short "Read and
  manage" button, instead of one letter a line.
- **Small things put right.** **Checked for you** now also catches `[TODO]`, `[TBD]` and
  `[Placeholder: …]` in any case, and no longer mistakes a link's own text, such as
  `[source-available](https://…)`, for a source ID. `source add --purpose messaging` on
  its own is refused in a plain sentence, because approved messaging marks a library
  reference or one blog's file and on its own would never be read. **Length** is offered
  only for new writing (write, outline, from an outline, from your files), reads "The usual
  length", "Short (about half)" and "In depth (about twice)", and names no style or
  capability that may not apply; `run create --length` for a review, a revision or ideas is
  refused. `run submit --gap` outside a draft or a handoff is refused in a sentence instead
  of being dropped, and a worker's refused result names evidence and gaps beside content
  and notes. **Needs you before publishing** lists each gap on its own line with quiet
  separators on opaque paper, and a long gap wraps at phone width.

- **Announcements that read like announcements.** A file can be **Approved messaging
  (the product's own claims)**, beside facts and examples: a messaging document, launch
  brief or release notes is written in the product's voice and the present tense, with
  only the limits it marks itself (preview, planned). A draft and a handoff keep source
  IDs and editorial placeholders out of the writing: each claim's source goes to the
  notes, and what you must still supply appears under **Needs you before publishing**;
  **Checked for you** fails a draft that still has one. A limitation is stated once,
  each capability gets what it does, how, what you can now do and an example, and
  **Length** asks for the style's own length, short or in depth. For maintainers:
  purpose and library role `messaging`, `stance` on payload sources (only when a run has
  messaging, so pins hold), the `writing-with-notes` response with `evidence` and `gaps`,
  `text_checks.reader_facing_notes`, `run create --messaging --length` and `run submit
  --gap`. Blog Studio 4.6.0; guidance needs runtime 4.6.0.

- **The companions, fully used.** A blog's brand export now carries the chosen author
  voice (`--voice-profile`), so the brand's `VOICE.md` names it; a tone-only run passes
  none, and a brand that refuses the voice is shown in its own words before anything is
  made. The writer is told what `research_bundle` is and that its IDs and digests are never
  words a reader reads. A goal that compares options asks the research for a comparison.
  **Bring the evidence up to date**, when asking for changes to the research, reads the
  sources again. For maintainers: `studio.voice_handoff`, `brand_skill.snapshot(...,
  voice)`, `Brand.export(voice_profile=)`, and the run's research stage keeps `refresh`.

- Finish authoring on the page: outline/revise/review start cards, complete idea development, Done checks and repurposing, and a revision-checked private Google Doc handoff that reconciles uncertain uploads.
- Apply review findings with the prior draft and history kept. Review notes open beside the text and show real voice, repetition, example and preservation checks. Uploaded files have individual team-library choices before sharing or use.

- Research stops now show the authored brief, independent check, gaps, partial sources
  and findings mapped to planning questions. Research requests describe the full rerun,
  recorded cost and saved downstream work before sending. Home preserves research defaults.
- Supplied-only guided blogs map claims to exact source passages with one correction
  instead of researching their own material. Web research gets a tool-less plan of at most
  eight questions. Saved legacy pipelines and from-files supplied-only runs retain their flow.

- **Where this run stops, and one name for each thing.** The last step of a new blog has
  a **Where this run stops** card: the level for this blog, the stops it makes, and
  **Use this for new work in every studio**; Settings has **Where new work stops**, saved
  at once and refused when another studio changed it meanwhile. A run says how many
  steps are left, where it next stops and what its jobs have cost (every stage job is now
  metered, not only research), and **Ask for changes** says what is drawn again and what
  that took last time. The last stage is the **Handoff**; **Publish revision** is
  **Record in team repository**; the research choice reads **No research**, **Only what
  you supply** or **What you supply and the public web** everywhere; the form says what
  research will read, what the tone does beside a voice, and each gate says what its
  decision does. The README lists Home's real start choices. For maintainers:
  `studios_config.update` takes a `guard`, the run view has `ahead` and `redo`, and stage
  jobs are kept in this computer's run state as `jobs`.
- **Research that can finish, and failures that say what to do.** Research the
  independent check refused is no longer thrown away: the draft report and the check's
  notes are kept on this computer, in the blog's `.studio-research-draft` folder (never
  shared), and the run lists **What the research check objected to**, grouped by kind and
  verdict with the first note of each. **Try again** continues from that draft for up to
  three more rounds and says what the last attempt took; research says "Round 2 of 3"
  while it works. A new blog stopped at research offers **Continue without research**
  instead of pointing at an Edit manuscript button it does not have. **Finish** asks
  first at every review level and says the draft is kept in the team library, then
  "Finished. Kept in the team library." A CLI failure points at **Status → Check this
  computer** and shows **What the assistant said**; a step out of time says how long a
  step may take and that the limit is in Settings. First-run setup opens **Writing
  preferences** and marks an assistant that is not installed.
- For maintainers: the run's local state carries `reason` (`cli`, `time-limit`,
  `research-check`), `said` (the last 20 stderr lines, kept in
  `.blog-runs/diagnostics/cli/<id>.json`, mode 0600) and `research` (`kept`, `refusal`,
  `round`, `phase`, `last`, `contract`, `from`); `said` is redacted and drops lines that
  echo the job, and is kept only for a CLI failure. The kept draft's `kept.json` ties it to
  the research stage's pin and saved version, and saving research by any path lets it go.
  Status carries `research_skipped` and `keeps_draft`. The page route `run-skip-research`
  drops the research stages (not while research awaits a decision) and records
  `research_skipped`; later jobs get `research_policy: none` and no
  `research_bundle`. `synthesis_research.generate` takes `progress`, and
  `blog_worker.metered()` collects the tokens and dollars a CLI reports. The refusal
  takes the shared contract's `groups` and `cause` when it has them.

- **A Google Doc with several tabs is read whole.** Adding a Doc link to a blog's files
  reads every tab, each under its own title, and the file row says which tabs were read.
  A link to one tab (the address Google Docs shows for that tab) reads that tab alone. Such
  a Doc used to be refused with a message about snapshots, and Start stayed grey without
  saying why; the files screen now says it needs one file with text.
- **One team library.** Every finished blog lands in the library when you choose
  **Finish**, as a reference and an example of its kind of post by its author; a second
  Finish updates the same item. Files added to a blog land there too unless you untick
  **Keep in the team library**. **Add to library** takes files, a list of links and a
  Google Doc in one sheet with a role, author and kind of post; **Each post's own
  author** reads every page's byline and groups the posts by author to rename, merge,
  complete, mark as voice samples and learn a voice from. The library filters by role,
  kind and author, and a selection learns a style or a voice or starts a blog with the
  items as examples. **From the library** on the files card picks items as facts or
  examples for one blog without changing them, and a learned kind of post pre-ticks the
  examples it was learned from. **Settings** names a default voice, and **Interview me**
  takes **Write as**.
- For maintainers: a source's `library` record carries `kind`, `origin_kind` and
  `article`; `library find` takes `--role` and `--kind`; `run create` takes `--example
  <id>` and, from the page, `library: [{id, role}]`; `source-role` changes a library
  reference in a new revision; the desk routes are `library-add-preview`, `library-add`,
  `library-add-author`, `library-add-samples` and `library-selection`; the personal
  writing default `voice` is saved from Settings, checked against `voice_before`. A Team
  Hub row is named with `location: hub` and checked out before use; `library-add` takes
  `retry` for failed links; `library-selection` saves nothing, and a confirmed learning
  job with `mark` makes its chosen items samples. A run reads every source at the
  revision it pinned, from `revisions/<n>/` when the source has moved on.
- Deleting a blog accepts its title as you type it: case, spacing, curly quotes and
  dashes no longer have to match the stored title exactly, and the sheet says when
  the text is not the title yet. Every card on **Blogs** has **Delete**.
- **Voices and styles.** A blog takes a voice (how you sound) and a style (the shape of a
  kind of writing), chosen as **Write as** and **Kind of post** when you start it. Eight
  starter styles for tech-industry writing are ready to use and editable, and a style can
  be learned from examples of a kind of writing by anyone. **Tools → Voices and styles**
  manages both in one place, and **Change the voice** switches a blog's voice, asking
  first when it already has writing. **More tools** is now simply **Tools**.
- **Write as someone else.** A voice belongs to one author, so a ghostwriter can keep a
  voice for each person they write for and start a blog with that person's voice and name.
- **Bring in writing, yours or an author's you write for.** Import a LinkedIn data export
  (profile and articles only), paste links or choose a links file of public posts and say
  whose they are, or use a source already in your references. Each becomes that author's
  sample, and the sheet offers to learn their voice, or a style, from them.
- **In chat, a blog takes your default voice** when you do not name one, as on the page,
  and a revision or review keeps its manuscript's own voice. Ask for no particular voice
  to write without one; a tone you give beside a voice nudges it, and a kind of post
  can be named too.
- For maintainers: styles are stored beside voices in a `styles` folder (and `.shared/styles`
  in a team workspace), starters are copied in only when saved, retired or used, and
  `library voice-links` takes `--purpose style-sample`. `run create` applies the default
  voice without `--profile`, `--profile ''` asks for none, and `--style <id>` pins a style.
- **Write from a brief** takes every file at once, like New blog from my files: the
  second step lists each file with how much text it has and what it is for, takes a
  Google Doc beside them, and keeps the saved references and research choice in their
  own disclosure. Files stay with the blog unless you keep them in your references.
  Oversized files are excerpted on every path, and a blog pins the files it was given
  so a deletion keeps them with it.
- **New blog from my files** asks what each upload is for: facts that may be quoted,
  or an example of the kind of post. Examples reach the assistant apart from the
  sources, with no citable ID; research never reads them; the draft and review say
  which passages were carried over from one, under **Checked for you**.
- **I know the point** starts a blog from files at the outline, from a title, the
  point and the reader, instead of three angles. **Write as** chooses the voice on
  the files screen as on the wizard's first step: your default voice, at the revision
  it pins, a saved profile or none.
- Under Balanced, a blog that starts from your outline stops for you at the draft
  before its package; so does a revision, and an existing blog after changes to its draft.
  A run that selected an inspiration source before this change goes stale, because
  its saved input pins change; review its saved version or ask for changes to go on.
- For maintainers: `upload` file entries take `purpose`; the `source-role` desk route;
  `run create --point`; `run-create` takes `revision` beside `profile`; `review_policy.automatic(..., first=)`;
  `text_checks.carried_over`; `synthesis_research.offered`.

## 4.3.0 — 2026-10-20

- Manuscript **More tools** adds voice learning, auditions and revisions; resumable
  interviews; channel copy; Google/local comparison; text history; citation/title
  workshops; local pre-publish reports and topic-overlap advice.
- Results remain reviewable. Local saves, shared delivery, Google sends, profile
  confirmation and draft approval stay separate. Source changes reject older output.
- Library status/collection filters and retirement undo improve recovery. Long
  sheets keep Close reachable, with the existing keyboard focus and phone layout.
- Optional `--compact` command results and a generated command inventory make CLI
  outcomes easier to consume without changing compatible full JSON.
- Git tree reads reuse exact immutable revisions within one bounded operation;
  nothing caches remote freshness or changes published history.
- See [capabilities](docs/capabilities.md), [privacy](docs/privacy-review.md) and
  [optional proposals](docs/optional-extensions.md) for limits and future scope.

## 3.0.0 — 2026-10-15

**For authors**

- Shared Settings conflicts now offer an explicit reload and retry. Reloading
  keeps local writing preferences and shows the current shared values.
- Joining a team checks for concurrent Settings changes before preparing the
  clone and before activating it. A refusal keeps the previous active workspace
  and the other studio's settings. Local writing saves preserve an unsupported
  shared assistant and its model/effort.

**For maintainers**

- Blog Studio, Training Studio and Presentation Studio now share one release
  number, and all three are 3.0.0. The major version marks that shared number;
  nothing authors rely on was removed, and existing blogs, voices and settings
  carry over unchanged.
- Refresh the backlog for the current page and shared workspaces; closed
  live-evidence issues are no longer described as implementation gates.

## 2.1.0 — 2026-10-15

**For authors**

- Add a brand skill's repository and release in Settings, select an installed
  skill, and install a checked release after confirmation, like Training Studio.
  Choose a brand and variant for each new blog; existing blogs retain their exact
  brand guides and keep the author's voice separate.

- Join one team repository alongside Training and Presentation Studio. Blogs use
  readable folders, one confirmed driver, explicit takeover/handover, decision
  sharing and numbered revisions. Selected legacy Hub work can be migrated while
  preserving its source. Shared studios settings live in one file, edited directly from
  Settings. Legacy local copies migrate without overwriting existing shared values.

- Open Blog Studio with a permanent shell command or Mac launcher, like Training
  Studio. Setup and the UI share computer checks with actionable next steps. Start
  commands find a supported Python and remember your selected writing workspace.
  Updates preserve custom launchers and wait until the running page is closed.

- Use Training Studio’s current page layout, navigation, three-step creation,
  progress stages, paper reviews and approval sheets, with Blog Studio modes
  for writing, outlining, revising and reviewing. Edit shared settings and local
  writing preferences in Settings, and compare a revision with its last approved version.
- Create and run guided blogs from the page, or work through the same stages
  with the skill in a conversation. Research questions, findings, outline,
  draft, review and export package each wait for your approval.
- Select your sources, voice, research scope and Codex or Claude CLI. Pause,
  stop, retry, download Markdown, ask for changes to an earlier stage, or
  continue the same blog in chat. Existing manuscripts can enter at review.
- Changed inputs invalidate decisions. Old page actions and late worker results
  cannot replace newer saved work. Runs and decisions share through the existing
  Hub; execution starts only on computers where you explicitly resume it.

**For maintainers**

- Releases are published with `bash scripts/release.sh` from a clean, current
  `main`. The `release.yml` workflow added in 2.0.0 is removed: the runner
  service that checks pull requests serves this repository only while its one
  approved workflow is the only active one, so a second workflow stopped every
  pull request check.
- `verify-tart.yml` is back to its approved content. `check.sh` now requires
  the linter whenever it runs under GitHub Actions, so the workflow does not
  have to ask for it.

## 2.0.0

Blog Studio is now installed as one complete skill. The earlier design, a small
bootstrap that fetched instructions from the repository at the start of every
blog, is retired.

**For authors**

- **Install and update from Releases.** Download `blog-studio-installer.zip`
  from the latest release and run `sh installer/install.sh`. Updating is the
  same step with a newer download.
- **No repository access or GitHub sign-in to write.** Setup and writing work
  offline. Git and the GitHub CLI are needed only for a Team Hub.
- **Starting a blog is immediate.** Nothing is fetched or copied per blog, and
  the `task-context` folder is no longer used.
- **Each blog records the version it was started with.** Say “Use the current
  guidance for this blog” to adopt the installed version; earlier reviews are
  then marked stale. Blogs started in 1.x keep opening and saving.
- **Setup is harder to break.** It no longer depends on a Homebrew path that
  disappears on a Python upgrade, and `check` reports a missing Python. A closed
  window or crashed setup no longer blocks the next run. An interrupted update
  is undone or completed. Running setup over a damaged installation replaces
  it. Finder's `.DS_Store` files no longer fail verification.
- **Backups stay out of skill folders.** A replaced folder moves to
  `~/.local/share/blog-studio/backups/`, so tools do not discover it as a
  second Blog Studio. Setup asks before moving anything.
- **Update, repair and check keep your tools.** Without `--target` they act on
  the tools chosen at installation.
- **Rollback works for every installed version**, including each 1.x release.

- **Team Hub stays usable as it grows.** Earlier drafts are shared once
  instead of with every save, so a blog no longer hits the Hub size limit after
  a few dozen saves. Local snapshot copies that nothing read are gone, and
  delivered saves leave the local queue.
- **An interrupted command no longer blocks the next one.** A second command
  waits briefly for the first instead of failing with "Workspace is busy".
- **No silent second version.** If a teammate shared a newer version of a blog,
  your save is kept on your computer and reported as held; you choose to
  continue from the shared version or share both and resolve them.
- **Clearer Hub failures.** A closed contribution review is retried on a new
  one; local Git problems are reported as such instead of as "offline"; an
  oversized source is refused at intake with the file and limit named.
- **The editorial desk only changes what you changed.** Saving an owner or due
  date no longer renews a stale "ready" decision, and saving a note no longer
  freezes a reference's tags. Marking a blog ready or published asks you to
  confirm.
- **The desk stays up.** A bad Word file, a damaged search index or one
  unreadable blog produces a message instead of a dropped connection, and a
  slow request no longer freezes every tab.
- **Importing earlier posts is cleaner.** A failed preview leaves no empty
  collection behind, refreshing a folder picks up new files, and re-importing
  does not duplicate posts.
- **You choose whether a reference is summarized.** Upload and import dialogs
  say that summaries send the document text through your signed-in writing
  CLI, and each has a checkbox to skip it. Opening the desk no longer turns
  summaries on by itself.

- **Google review can always be continued.** A timed-out or refused
  suggestion, a comment batch interrupted by a rate limit, and an uncertain
  "Apply edits" can each be verified and resumed instead of blocking the blog.
  Review edits are numbered per blog, so a second round does not reuse "Edit 1".
- **Edits on both sides are merged.** When you and a teammate changed different
  paragraphs, pulling combines them; only a paragraph changed on both sides
  asks you to choose. With a linked Doc, "Proofread" saves findings and leaves
  your draft alone, so rejecting a suggestion no longer ends in a conflict.
- **Fewer false stops.** A teammate's pending suggestion no longer blocks
  starting from, pulling, or commenting on a Doc. Renaming a Doc is not treated
  as a change. Strikethrough, underline, superscript, code and titles survive a
  pull, and inserted words no longer inherit a neighboring link or bold.
- **Google data stays closer to home.** A Doc's raw data, which can include
  collaborators' comment threads, stays on your computer instead of syncing to
  the Team Hub. Staged captures are cleaned up, writes are limited to Docs
  linked to a blog, the Google account is remembered per workspace, and sign-in
  no longer switches the account gcloud is using.

Known limits: a Doc with tables, images or footnotes cannot be pulled while
suggestions are pending; a Hub that was already large keeps its earlier history;
and everyone sharing a Hub should update to 2.0 together. Google behavior was
verified against recorded fixtures, not a live account.

**Upgrading from 1.x:** run the 2.0 installer; it upgrades in place. Until
then a 1.x installation answers a new blog with “This guidance needs a newer
local Blog Studio runtime. Run the installer update.” Existing 1.x blogs can
still be resumed there.

**For maintainers**

- One version source: `skills/blog-studio/VERSION`.
- `bootstrap/`, `sync_guidance.py` and the committed `dist/` archives are
  removed. `scripts/build.py` builds reproducible archives into the ignored
  `build/` folder and replaces both packaging scripts.
- `release.yml` tags and publishes a GitHub Release when `VERSION` changes on
  `main`. `ci.yml` and the release run the single list in `scripts/ci/check.sh`.
- `studio.py article guidance` takes `--id` and optional `--adopt`; `--task`
  and `--cached` are gone. `readiness --online` is accepted and does nothing
  extra.
- `guidance/manifest.json` stays as the upgrade notice for 1.x installations.

## 1.0.0 to 1.15.0

Condensed from the per-release notes that used to live in the installation
guide. All of these releases used the bootstrap design.

- **1.15** Deep research: “Research this topic”, “Fact-check” and saved research
  briefs, with the research workflow bundled in the installer.
- **1.14** Normal Git checkouts for Team Hubs under `~/blogs/`, visual import of
  earlier blogs in the editorial desk, reusable reference memory, and “Push
  feedback as comments”.
- **1.13** Drafts, originals, reviews and history kept together in readable
  folders inside each Hub.
- **1.12** Editorial desk and the shared team blog library.
- **1.11** “Start from this Google Doc”, which keeps the original Doc linked as
  the working document.
- **1.10** Readable review comments when native Google suggestions are
  unavailable, with “Show review edits” and “Apply edits 2 and 4”.
- **1.9** “Push as suggestions”, with a freshness check of the linked Doc first.
- **1.7 and 1.8** Short commands, status cards and writing defaults; faster
  local resume and checks.
- **1.5 and 1.6** Formatted Google Docs round trips, optional house style, live
  Google freshness and Doc links in the Hub library.
- **1.2 to 1.4** Google Docs workflows and transfer checkpoints, the gcloud
  route, guided writing and the readable team library.
- **1.1** Team Hub: shared blogs, sources, voices and team rules in a private
  repository.
- **1.0** Guided installer and pinned guidance updates.
