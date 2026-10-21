# Voices, styles, and deleting from the Blogs page

Status: draft for review, 2026-10-21. Nothing here is built yet.

Three requests from the Blog Studio page, in the order they should land:

1. The delete confirmation sheet can leave a person stuck with a greyed-out
   Delete button.
2. A blog should be deletable from the **Blogs** page, not only from the last
   screen of its run.
3. Bring back BlogForge's "import a LinkedIn export and learn my voice", add
   "learn from links to specific posts", and split what is learned into two
   things: a **voice** (how one person sounds) and a **style** (a kind of
   writing, such as a product announcement). Ship a starter set of styles for
   writing in the tech industry. A new blog then takes a voice, a style, a brand
   and sources, and runs as it does today.

## 1. The delete sheet that locks up

### What was found

The sheet in `assets/management/runner.js` (`sDeleteSheet`) enables its Delete
button only when the typed text, trimmed, is character-for-character equal to
the blog's stored title. The server (`blog_delete.check`) makes the same exact
comparison. While the sheet is open, the rest of the page is `inert`, so when
the button never enables the page feels locked. Escape and Cancel do still
close it.

In a disposable workspace the sheet worked: typing the title enabled the button
and the blog moved to **Recently deleted**. The stuck state therefore comes from
the title itself. Anything that makes the stored title differ from what a
person would type defeats it: a trailing space, two spaces, a non-breaking
space, a curly apostrophe or dash, or a title picked from an "ideas" result or
a Google Doc that carries such characters. Titles are also compared
case-sensitively.

The second possibility, that the button was pressed and the request hung, is
ruled out by the screenshot: a pressed button reads "Deleting…" and this one
still carried the full title. (If the person did press it and nothing moved,
`blog_delete.delete` waits up to 30 seconds for a working job to end, and the
page reports "busy" for other requests meanwhile. That is worth a second look
only if the normalized comparison does not resolve the report.)

### Change

- Compare titles after normalizing both sides the same way on the page and the
  server: Unicode NFKC, whitespace collapsed to single spaces, trimmed,
  case-folded, and typographic quotes and dashes mapped to their plain forms.
  The server stays the authority; the page only decides when to enable the
  button.
- While the text does not match yet, show a quiet hint under the field,
  "Not the title yet", so the disabled button explains itself.
- Keep the typed-title safeguard. No "use the title shown" shortcut.
- The server's `MISTITLED` message stays as it is.

### Tests

- `tests/test_blog_runner.py`: delete accepts a title typed with plain quotes,
  different case and collapsed spaces against a stored title with curly quotes,
  double spaces and a trailing non-breaking space; still refuses a different
  title.
- `scripts/ci/check-management.cjs`: the sheet enables the button for the
  normalized match and shows the hint before that.

## 2. Delete from the Blogs page

### Change

Each card on **Blogs** (`sBlogCard`, and the saved-draft cards for ordinary
blogs) gets a quiet **Delete** action beside its primary button. On a phone it
folds into the card's "⋯" menu, following `sFold`. It opens the same
`sDeleteSheet` with `{id, title, status, team}` from the listing; the sheet
already fetches the blog's current version token when none is supplied. After
the deletion the Blogs page re-reads and the blog appears under **Recently
deleted**, as today.

Home does not get the action. Home is for what needs attention; Blogs is where
a blog is managed.

### Tests

- `check-management.cjs`: the Blogs page renders a Delete control per card, it
  opens the sheet with the card's title, and a successful delete re-reads the
  list.

## 3. Voices and styles

### Words

- **Voice**: how one person sounds. Learned from writing they authored. The
  person may be you or someone you write for: a workspace holds a voice per
  author, each named for that author, and a blog can be written in any of
  them. That is how ghostwriting works here: learn Nick's voice from Nick's
  posts, then start a blog with Nick's voice and, if you like, Nick's name as
  its author. A voice stays what Blog Studio has today under `profiles/`: a
  guide (`VOICE.md`), optional background, explicit rules, sample IDs,
  revisions, provisional or confirmed state, and a pinned revision per blog.
  Every sample records whose writing it is.
- **Style**: the shape of a kind of writing, independent of who writes it. A
  product announcement, a how-to, a comparison. Learned from examples of that
  kind, by anyone, or shipped as a starter. A style says structure, length,
  opening and closing moves, heading habits, what belongs and what does not,
  and the register a reader of that kind expects. It never says "I" or carries
  biography.

A blog can take a voice, a style, both or neither. Tone text remains for the
"neither" case and as a nudge on top of either.

### Storage

Styles get their own group beside profiles, built the same way so the existing
revision, pin and read code applies with the group name as the only variable:

```text
styles/<id>/record.json     id, name, kind ("seed" | "learned"), revision, status
                            (provisional | confirmed | retired), sample_ids,
                            created_at
styles/<id>/STYLE.md        the guide
styles/<id>/revisions/<n>/  record.json and STYLE.md as saved
```

`studio.py` gains `style_command` (create, save, show, retire) and
`style_pin`, mirroring the profile ones. `list styles` joins the `list`
command. `studio.initialize` creates the folder.

Sources used to learn a style take a new purpose, `style-sample`, next to
`voice-sample` in `studio.PURPOSES`. One uploaded or fetched post may carry
both purposes when it is the author's own and also a good example of a kind.

A blog's run record gains `style: {style_id, revision}` beside `voice`. The
pin is taken when the run is created, exactly as the voice pin is, and a later
style edit does not change an existing blog.

Team sharing: v1 keeps styles on this computer and in a team workspace's Git
folder (the folder is committed like `profiles/`). Publishing styles to a Team
Hub as a new item kind is left for a follow-up; `GROUP_KIND` in
`hub_workspace.py` is not extended now. The Hub schema says an item's kind never
changes, so this is additive later.

### Starter styles

A set of styles for writing in the tech industry ships with the skill under
`skills/blog-studio/references/styles/seed/<id>.md`, each with a short front
matter block (name, one-line description) and the guide body. On the first
read of `styles/` in a workspace (or when **Author voices and styles** is
opened), any seed not yet present is copied in as a `seed` style, revision 1,
status `confirmed`, so it can be used at once and edited like any other. A
seed a person retires stays retired; it is not copied back.

The starter set, drawing on the templates already vendored under
`references/upstream/claude-blog/skills/blog/templates/`:

| id | Name | Shape in one line |
| --- | --- | --- |
| product-announcement | Product announcement | Lead with what is new and for whom, one proof point, availability, next step |
| release-notes | Release notes and changelog | Grouped, scannable changes with version, dates, upgrade notes |
| technical-deep-dive | Technical deep dive | Problem, approach, trade-offs, what was measured, what is still open |
| how-to | How-to and tutorial | Prerequisites, numbered steps with checkpoints, a finished state, troubleshooting |
| point-of-view | Point of view | A stated position, the strongest objection, evidence, what to do differently |
| customer-story | Customer story | Situation, constraint, what changed, measured outcome, the customer's words |
| comparison | Comparison and evaluation guide | Criteria first, fair treatment of each option, a recommendation by situation |
| lessons-learned | Postmortem and lessons learned | Timeline, contributing causes, what changed, without blame |

Each guide is guidance about shape, not sample prose, which keeps it within the
repository's rule against writing content. Each ends with "Does not belong"
and "A reader expects" lists.

### Learning a voice or a style

One tool-job kind per thing learned: the existing `voice-learn` and a new
`style-learn` in `tool_jobs.KINDS` and `article_tools.request`/`apply`. Both
start from selected ready sources, both return an editable guide and a labeled
synthetic audition, both save provisional until confirmed. `style-learn`
guidance tells the worker to describe the kind of writing and to ignore who
wrote it: structure, moves, length, headings, register, what every example
shares and what varies. It must not produce a voice.

Three ways to get samples in, all landing as sources so the existing library
rules apply. Each voice sample carries the author's name in the source's
`author` field, and learning a voice proposes that name for the profile.

1. **Upload a file**, as today, with purpose `voice-sample` or `style-sample`
   and the author's name when known.
2. **Import a LinkedIn export.** The packaged `linkedin_import.py` already
   parses `Profile.csv` and `Articles/*.html` from the zip, reads nothing else,
   and refuses nested or oversized archives. It additionally reads the
   person's name from `Profile.csv`. New: an `upload` entry kind
   `{linkedin: <base64 zip>}` handled in `management.upload`, which calls the
   parser, saves the headline and summary as an `author-background` source,
   and saves each article as a `voice-sample` source named "LinkedIn ·
   <title>", all with that person as author. The export is usually your own,
   but a colleague can hand you theirs; the sheet shows whose it is and lets
   you correct the name. The sheet then offers to learn that person's voice
   from the articles, with the background attached; the same permission
   checkbox as today gates the job. The export is a voice input only; a style
   can still be learned later from the sources it created.
3. **Add links to posts**, pasted or as a text file. This is how a ghostwriter
   usually starts: a file such as `darin-zook-blog-links.txt` with one link
   per line.
   - **The list.** The sheet takes pasted text or a `.txt` file. One link per
     line; blank lines and lines starting with `#` are ignored, as are list
     markers and angle brackets; `http` links are upgraded to `https`;
     duplicates are dropped after canonicalizing (lowercase host, no
     fragment); anything else unusable is listed with its line number and
     reason. Up to 256 KiB and the library's post limit per list.
   - **Whose writing.** For voice samples the sheet asks whose writing the
     links are, prefilled from a file name such as
     `darin-zook-blog-links.txt` as "Darin Zook" (trailing words like blog,
     posts and links are dropped) and editable. Style samples need no author.
   - **Reading.** Links go through the reference library's own `urls`
     import, by way of `voice_links` (first built on the local branch
     `claude/voice-from-links-wip` and merged here): the list's common site and
     folder become the import's scope, and each new page is fetched once with
     the library's pinned fetcher, in batches of 25, and saved in the library
     under a collection named "Published posts by <author>". A list that mixes
     sites asks which site to import. One fetcher serves the library and voice
     intake; the trade-off is that imported posts also appear among the
     library's references.
   - **Check first.** Before anything is fetched, the sheet shows the site,
     the links already in the library and the links it will fetch, and the
     import is bound to that check.
   - **Author check.** Where a page names its author (JSON-LD `author`,
     `meta` author tags, `rel="author"`, or a byline element), the name is
     compared with the chosen author, ignoring case, accents, "By", word
     order and middle initials; a page listing several authors matches if
     any of them does. A mismatched post is left out and reported with the
     name it gives; **Keep as sample** keeps it. Style samples skip this check.
   - **Already here.** A link already in the library, including one only the
     Team Hub holds, is reused instead of fetched; it gains the sample purpose
     in a new source revision. Repeating the same list continues the same
     import, and failed links can be tried again without fetching the rest.
   - **Report.** One row per link: saved as a sample, already in your
     library, held back for a different byline, or could not be read and why.
     LinkedIn post links are refused with a note pointing at the export. No
     sign-in, no private pages.
   - **Chat.** `library voice-links --file <txt> --author <name> [--import]`
     runs the same check and import from a conversation; `--purpose
     style-sample` takes examples for a style.

Permission is the person's to give: the checkbox before a learn job says the
samples are writing you have permission to analyze, whether yours or an author
you write for.

### The page

- **More tools → Author voices** becomes **Voices and styles**, two tabs or
  two sections in one sheet: Voices (one card per author, as today, plus
  **Import a LinkedIn export** and **Add links to posts**, which asks whose)
  and Styles (starter and learned, each
  with Read, Edit, Audition, Retire; plus **Learn a style from examples** which
  takes files or links).
- **New blog → Voice and brand** becomes **Voice, style and brand**: a Voice
  select, a Style select (starter styles listed first, "No particular style"
  default), Tone, Author, Brand. Both selects show provisional state in the
  option label as the voice select does.
- The writing run's **About this blog** card names the pinned voice and style.
- Chat gets the same: `references/voice-flow.md` grows a short style section
  and `workspace/profiles.md` a styles sibling, so the skill can create, learn
  and pin styles from a conversation.

### The worker

`article_basis` in `article_tools.py` and the run payload in `blog_runner.py`
add a `style` block beside `voice`: the pinned `STYLE.md` text and the style
name. `blog_worker.POLICY` gains one paragraph: the style says the shape of
the piece; the voice says how its author sounds; where they conflict on
wording, the voice wins; where they conflict on structure, the style wins;
neither invents facts. The outline step uses the style's structure; the draft
step uses both.

### Errors and limits

- A retired style cannot be pinned to new work; existing blogs keep theirs.
- A learn job with fewer than two readable examples still runs but the guide
  is labeled thin, as voice learning does with one sample.
- Links: an `http` link is upgraded to `https`; links resolving to a private
  address, over the library's fetch limit, or outside the checked site fail
  one by one; a list over 256 KiB or the library's post limit is refused. A
  post whose byline names someone else is held back until the person keeps it.
- LinkedIn: refused over 25 MB of selected material, nested twice, or without
  profile or articles, with the parser's existing messages.
- Seeding never overwrites an edited starter: a seed is copied only when its id
  is absent.

### Tests

- `tests/test_blog_studio.py` or a new `tests/test_styles.py`: style create,
  save, show, retire, pin; seeding copies missing starters only and leaves an
  edited or retired one alone; `list styles`.
- `tests/test_editorial_tools.py`: `style-learn` request and apply, provisional
  then confirmed; `voice-learn` from LinkedIn-created sources.
- `tests/test_blog_runner.py`: a run created with a style pins its revision;
  the payload carries both voice and style; a later style save does not change
  the run.
- Upload: a synthetic LinkedIn zip (profile row and two article HTML files)
  creates the sources and background.
- Links: the merged `tests/test_voice_links.py` (14 tests with a stub
  fetcher: parsing, scope, mixed sites, limits, bylines, name matching, keep,
  retry, re-run, library reuse, batches past 25, Team Hub sharing) plus one
  for style samples, which skip the byline check and keep the post's author.
- `check-management.cjs`: the wizard shows the Style select and sends `style`;
  the Voices and styles sheet lists both groups and opens the import flows.
- Full `scripts/ci/check.sh` once before completion, in a disposable home.

## Order of work

1. Delete sheet fix and Blogs-page delete (small, independent, ship first).
2. Styles storage, seeding, pin, worker payload, wizard select.
3. Learning: `style-learn` job, link intake, LinkedIn intake, sheet changes.
4. Docs: `docs/runner.md`, `README.md` "Voice and style", skill references.

## Open questions

1. Confirm the symptom: was the Delete button greyed out with the title typed
   (what the screenshot shows), or did you press it and the page then hung?
2. Should seeded styles be **confirmed** from the start (usable at once,
   recommended) or **provisional** until someone reads them?
3. Team Hub sharing of styles: fine to leave for a follow-up?
4. Any starter styles to add or drop from the table above?
