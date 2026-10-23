# Team library, voices and a usable layout for Blog Studio

The owner's review of the Team library screen: it needs a select all; adding posts and
learning voices are confusing (Learn a voice, Add links to posts, Import a LinkedIn
export, Upload an authored sample and Import old blogs all overlap); and the screens are
not in a usable workflow order. This design keeps every function, gives each screen one
primary action, and separates two voice workflows.

## 1. Select all

The library list header carries a "Select all" checkbox for the rows the current filters
show on this page. When anything is ticked, a selection bar appears in the toolbar
material (glass) and stays in view: below the toolbar on a desktop, at the bottom above
the tab bar on a phone. It holds:

- the count, "N selected";
- "Select all N on this page", while some rows on the page are unticked;
- "Select all M matching", when the filters match more items than one page shows. The page
  asks the server for every item the same filters match (`GET /api/library-matching`, up to
  500) and ticks them all;
- the three actions as before: Learn a style from these, Learn a voice from these, Start a
  blog with these as examples (the primary action);
- Clear.

The matching rule. A tick is a tick: ticked rows stay ticked when you page and when you
change the filters, and the count includes rows you cannot currently see. "Select all M
matching" ticks what the filters match at that moment; changing the filters afterwards
neither adds to nor removes from the selection. Clear empties it. The bar says this in one
quiet line when ticked rows are hidden by the filters ("2 of them are not in this view").

Learning reads up to twenty readable items (the server names the rest, as today), so the
learn actions accept up to 500 ticked items. A blog takes up to 50 examples; with more
ticked, Start a blog says so instead of sending.

## 2. Two voice workflows

### 2a. Bulk: the team library

**Add to library** is the bulk path. Its one sheet takes files, a text file of links or
pasted links, and a Google Doc. Each post's text, title, byline and date are fetched and
stored. "Each post's own author" is now the default for the author; one typed author and
no author remain choices. The sheet also offers the larger sources that had their own
buttons: import a whole blog, site, feed, sitemap or export (the existing import dialog,
which replaces "Import old blogs"), and upload one file to summarize and tag it or to start
an editable blog from it (the existing upload dialog, which replaces "Upload").

**Create voices for every author** is a new action, offered under the Team library's lede,
on the Voices screen, and on the result of an Add to library. Its sheet lists every author in
the library (local and Team Hub items, retired items left out, authors folded with the same
name rules as the add's author groups) with their post count and readable count:

- an author with two or more readable posts is ticked;
- an author with fewer than two readable posts is listed, unticked and not tickable, with
  the reason ("Only 1 readable post; a voice needs at least two");
- an author who already has a voice (same name, not retired) is labelled "Update
  <name>'s voice"; their job updates that profile with a new provisional revision instead
  of creating a second voice.

One permission box ("I have permission to analyze this writing with my selected
assistant") and one button ("Create 2 voices and update 1") confirm the whole batch.
`POST /api/library-voices` then queues one `voice-learn` tool job per ticked author on the
existing single-worker queue, each reading up to 20 of that author's readable posts, newest
first. The posts become that author's voice samples only at this confirmation, as the
library selection's learning does (`mark`). The operation is idempotent: the batch
operation plus the author names each job's operation, so sending again returns the same
jobs. The sheet then shows each author's job status (Waiting to start, Working, Ready for
your review, Stopped) and, when ready, "Review <name>'s voice", which opens the usual job
sheet: save it as provisional or confirm it. Saving returns to the batch.

### 2b. One author: the Voices screen

**Create a voice** replaces the four entry points (Learn a voice from samples, Import a
LinkedIn export, Add links to posts, Upload an authored sample) with one guided sheet in
the order a person works:

1. **Whose voice is this?** The author's name.
2. **Add their writing**, from any of: links to their posts (a text file or pasted; the
   existing voice-links check and import), uploaded posts (several files at once, saved as
   this author's samples), a LinkedIn export ZIP (the existing import; About becomes
   background), or posts already in the library (the candidates, filtered to this author
   and to posts with no author; others are under a disclosure).
3. **Choose up to 20 samples.** Everything added above lands in this one list, ticked.

Then the permission box and **Build a provisional voice**. Every source returns to this
sheet with its new samples ticked. "Write a voice guide" stays as a secondary action.

**Create a style** has the same shape for a kind of writing: name it, add examples (links
to examples, uploads, from the library), choose up to 20, build. "Write a style guide"
stays secondary.

Both workflows end at a provisional voice to audition and confirm, as today.

## 3. Layout and workflow order

Rules, written down for the other studios in `docs/design/golden-gate.md` ("Layout rules"):
a screen's toolbar holds its title and at most one filled (primary) action, with
secondary actions as plain buttons beside it; a one-sentence lede opens the page; content
follows in the order a person works; filters sit in one row with rarely used ones under
"More filters"; a selection bar appears only while something is ticked, in the toolbar
material; lists are opaque cards or a quiet table; sheets are the only transient material.

### Team library (and the other legacy views)

The legacy views (All blogs, Review findings, Team library, Team memory) keep their
functions but take the shell's layout: the toolbar carries the title, the back button,
the view's primary action and "Library and team tools" (renamed from "Editorial tools", the
same sheet that Blogs opens). The page starts with the one-sentence lede, then the Hub
access line when a Hub is selected (with Check access and Refresh Hub), then one filter row
and the list.

| View | Primary action (toolbar) |
| --- | --- |
| All blogs | New blog |
| Review findings | none |
| Team library | Add to library (Create voices for every author sits under the lede) |
| Team memory | Add memory |

Team library filter row: Search, Role, Kind of post, Author, Status, then Search (a plain
button). "More filters" holds Collection ID. On a phone only Search shows, with a Filters
button that opens the rest. The list is a quiet table: the tick, the
title (with the original post's link), author, role and kind, status, and one action
(Review details). At phone width each row becomes a card.

### Other screens

- **Home**: Needs you, In progress, Saved drafts, What would you like to do?, Set up
  before you write, Finished drafts. The toolbar keeps one primary (New blog, or Review when
  something waits).
- **Blogs**: titled "Blogs" like its navigation item; a lede; primary New blog;
  secondary Library and team tools.
- **Voices and styles**: the Voices navigation item opens a screen (it opened a sheet over
  whatever was showing). Toolbar: Create a voice (primary), Create a style. Cards: Voices,
  Styles, and Every author in the team library (Create voices for every author). The same
  content still opens as a sheet from a blog's Tools, where a voice can be applied to that
  blog.
- **Settings**: shared settings and where new work stops, then writing preferences, step
  time limit and workspace, with Save at the end of that form; then "Elsewhere in Blog
  Studio": Voices and styles (opens the screen), Brand settings, Team sharing. Settings is a
  sidebar screen, so it has no Back button.
- **Status** and **Settings**: Team sharing's card offers Refresh Hub when a Hub can be
  refreshed (it sat in the Team library header).
- The run screen, the gate, the wizard and the files screen already follow the rules (one
  primary in the toolbar or at the end of the form, steps in order); they keep their layout
  and take the shared spacing.

### Moved controls

| Control | Was | Now |
| --- | --- | --- |
| New blog | Team library header | Home, Blogs and All blogs toolbars (unchanged there) |
| Refresh Hub | Team library header | The Hub access line on the library views; Team sharing on Status and Settings |
| Upload | Team library header | Add to library → "Upload one file to summarize, tag or start a blog" |
| Import old blogs | Team library filter row | Add to library → "Import a whole blog, site or feed" |
| + Add to library | Team library filter row | Team library toolbar (primary) |
| + Add memory | Team memory filter row | Team memory toolbar (primary) |
| Editorial tools | Legacy view toolbar | Same place, named Library and team tools |
| Collection ID filter | Filter grid | More filters |
| Learn a voice from samples, Import a LinkedIn export, Add links to posts, Upload an authored sample | Voices and styles | Create a voice (each is a source in step 2) |
| Learn a style from examples, Add links to examples, Upload an example | Voices and styles | Create a style |
| Open voices and styles (Settings) | Opened a sheet | Opens the Voices screen |

## Not changed

Permissions, provisional/confirmed voices, the tool-job queue, sharing, and every route's
refusals. No job starts without the permission box. No new dependency and no build step.
