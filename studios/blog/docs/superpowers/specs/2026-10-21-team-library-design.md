# One team library: design

**Date:** 2026-10-21. **Owner's words:** "maybe it makes sense to have a team blog library
where blogs we write go, but also we can upload or provide weblinks or google docs and they
go into a repo in which we can then select out of as type of blog guidance instead of
re-adding them for every blog."

**Decisions taken with the owner:** a run uses both a learned style and the posts it was
learned from; every finished blog and every file added to a blog lands in the library on
its own. The styles work on `claude/blog-studio-features-import-e662c9` lands first.

## What exists

- The library (`blog_library.py`): references shared through the Team Hub and the team
  repository, with "Import old blogs" (folder, website, feed, sitemap, JSON export, list of
  links) and the voice-from-links upload. A source record carries `purposes` (`reference`,
  `inspiration`, `voice-sample`, `style-sample`, `material`), `author`, and `library`
  metadata (`historical`, `published`, `topics`, `products`, `collection`, `identity`,
  `canonical_url`).
- Roles on upload (2026-10-21): Facts or Example of the kind of post, per file, on the
  files screen and the wizard; examples reach the writer apart from the sources.
- Styles (other session): a kind of post as a reusable guide, starter or learned from
  `style-sample` sources through a `style-learn` job, pinned to a run as `style`.

## What is missing

- A finished blog never lands in the library; the next announcement needs the last one
  uploaded again.
- The wizard's saved-references list is flat and every tick is a fact.
- Links and Google Docs enter only as material for one blog, or as voice samples.
- Nothing connects a learned style to the posts it was learned from at run time.

## Design

### 1. One library, one record

Every library item is a source record with:

| Field | Meaning |
| --- | --- |
| `purposes` | its role: `reference` (facts), `inspiration` (example), `voice-sample`, `style-sample`; several allowed |
| `author` | who wrote it |
| `library.kind` | the kind of post: a style id (starter or learned) or none |
| `library.published` | the date, when known |
| `library.origin_kind` | `written-here`, `upload`, `link`, `google-doc`, `import` |
| `library.article` | the blog it was written as, for `written-here` |

Shared as references are today (`share()`, Hub projection, team repository).

### 2. Four ways in

1. **On Finish.** `blog_runner` saves the final draft as a library source: purposes
   `['reference', 'inspiration']`, author = the run's author, `kind` = the run's style,
   `origin_kind` = `written-here`, `article` = the blog id, content = DRAFT.md as published
   text. Idempotent: a second Finish updates the same source (new revision), never a copy.
   Deleting the blog keeps the library copy; restoring it re-links.
2. **Files added to a blog.** The files card's "Keep in my references" is on by default
   and reads "Keep in the team library"; an item kept lands with its role and the run's
   kind and author. "Just this blog" (unticked) keeps a file as material, as today.
3. **Add to library.** A sheet on the library screen: files (many), a pasted or uploaded
   list of links, or a Google Doc link; then role, author, kind of post. Links go through
   the existing library import (`urls`) with the voice-links fetcher and scope check;
   Google Docs through `google_intake.material` then saved as a reference. Every item is
   listed with its text size and byline before it is kept.

   **A list of links by many authors.** Owner's words: "just like I can import Darin
   Zook's posts, we should be able to pass a text file of URLs for all the blogs we want in
   that library; then you pull the author and they become sample posts for an author as
   well." The author field offers "Each post's own author" beside a typed name. Then:

   1. *Import first.* Bylines are known only once a page is fetched, so every link is
      imported as a reference (plus `inspiration` when that role is chosen), split by
      site scope when the file mixes sites, with `library.author` = the published byline
      from `voice_links.bylines`.
   2. *Review the authors.* The sheet groups the results by author, folding variants with
      `voice_links.same_author` ("Darin Zook · 21, Sam Rivera · 3, No byline · 2"). The
      person can rename a group, merge two groups, or set an author on a no-byline row.
      A post with no byline, an organisation byline, or several bylines is held for the
      person to decide and counted for nobody until then.
   3. *Mark as samples.* One choice, on by default, adds `voice-sample` to every post in a
      named group (a new source revision through `source-purpose`, which no longer stales
      a run that pinned the source). Each group then offers "Learn <name>'s voice", with
      the existing confirmation before any learning job.
4. **Import old blogs** stays as it is for bulk imports.

### 3. Picking from the library

The "Your files" card (wizard and files screen) gains **From the library**: a sheet with
role, kind and author filters and a search box, listing items with title, author, date and
role. Ticked items join the same list as uploads, each with its role pre-set from the
library (changeable for this blog only; the library record is not changed). The run pins
them as it pins any source; nothing is copied.

When the chosen kind of post is a learned style, its `style-sample` sources are pre-ticked
as examples (up to eight, newest first) the moment the style is chosen; the person unticks
any. A starter style pre-ticks nothing.

### 4. The library screen

Filters for role, kind of post and author beside the existing status and collection
filters; a selection on the rows; three actions on a selection: **Learn a style from
these** (a `style-learn` job), **Learn a voice from these** (`voice-learn`), **Start a blog
with these as examples** (opens New blog from my files with the items ticked as examples).

### 5. Enforcement and sharing

Unchanged: examples reach the writer without a citable ID and the carried-over check runs.
Library items are shared as references are; material kept out of the library never is.

## Out of scope

Styles themselves, style learning and the Voices and styles sheet (other session);
publishing from the library; editing a library item's text.

## Testing

- Runner: Finish saves one library source with the fields above; a second Finish updates
  it; delete keeps it; a run that pins library items reads them with their roles.
- Management: Add to library with files, links and a Google Doc; refusals (no role, bad
  link, scope); the files card's keep default; the library filters and the three actions.
- Page journeys: Add to library sheet; From the library picker with filters and
  pre-ticked style samples; library actions.
- Team: a library item lands in the Hub and the team repository with its purposes, kind
  and author (fixture repository).
