# Write on the page or in a conversation

See [the manuscript workflow](manuscript-workflow.md) for focused editing, supplied
outlines, idea development, and selected Google suggestions or comments.

Blog Studio supports both. On the page it starts your selected Codex or Claude
CLI for each piece of writing, saves the result and waits for you. In a
conversation your assistant writes it with you. Both use the same blog folder,
stages and decisions.

## Open the page

On a Mac, double-click **Open Blog Studio.command** in your home Applications
folder. On Mac or Linux, run the installed command:

```sh
sh ~/.local/share/blog-studio/studio
```

It finds a supported Python and opens the page. It starts with
`~/blogs/.blog-studio`, or the workspace you last chose with
`sh ~/.local/share/blog-studio/studio --root <absolute-workspace>`.

You can also ask your assistant to **“Use Blog Studio. Open the page.”** From a
source checkout, the Python entry point remains available:

```sh
python3 skills/blog-studio/scripts/studio.py --root "$HOME/blogs/.blog-studio" manage --open
```

Use Python 3.11 or newer. Keep the terminal open. The page runs only on this
computer, with a private session link; closing the browser does not stop work.
Stopping the terminal stops its worker. Reopening resumes runs you had enabled
on this computer, from their last saved stage.

## Your first blog

The page follows Training Studio's layout: **Home**, **Blogs**, **Voice guides**,
**Status** and **Settings**, with the same glass navigation and toolbar and opaque paper
for reading and editing. Home groups **Needs you**, **In progress** and **Finished**.
Settings edits shared values for all studios and local writing preferences for future
blogs; existing blogs keep their choices. **Status → Check this computer** shares setup's
read-only checks and next steps. You can run the same report with
`sh ~/.local/share/blog-studio/studio check`.

Choose **New blog**, or one of Home's tasks (**Write from a topic or my documents**, **Work from my
outline or notes**, **Edit or polish a draft**). A new blog is always made on the writing
desk. A topic or an outline takes three steps; a draft takes one screen (below):

1. **What are you writing?** A card for each kind of post, with its usual shape and
   length, and **Something else**.
2. **Sources and settings.** Files, links, Google Docs and team library posts, each with
   its role: facts that may be quoted, approved messaging (stated as the product's own
   claims) or an example of the kind of post (its shape, never its facts). They stay with
   this blog; one with **Keep in the team library** ticked goes to the library when you
   press Start. For new writing, **Search my sites** and **Search the web too** research
   before the outline. They start as **Settings → Writing preferences → Research for new
   blogs from** ticks your sites and the public web (your documents are always read; your
   sites only when the shared list has any), and you can change them for this blog. Both are
   off unless ticked there. **Length** asks for the usual length, short or in
   depth. **Tone** says how it sounds.
3. **What do you have?**
   - **A topic**: a working title, who it is for and the point to make. **Suggest
     three angles** reads your sources and offers three cards; pick one and edit its
     wording, or type your own point.
   - **An outline or notes**, pasted or uploaded: **Write from my outline** writes the
     draft next; **Shape an outline with me first** opens the outline on the desk.
   - **A draft** switches to the polishing screen.

**Edit or polish a draft** is one screen with no step tabs and no kind of post to choose:

- **Your draft**, pasted, uploaded or from a Google Doc (every tab is read, and the Doc is
  not changed). The title is optional.
- **What should happen first**: **Proofread and tighten** (the default, with no kind of
  post), **Just give feedback** (Finishing's **Feedback without a rewrite** starts as the
  desk opens: comments beside each part, and nothing in the text changes), **Reshape to
  fit a kind of post** (only this one shows **Kind of post**, and needs one) or **Leave
  it as it is**. The opening is worked on with the sections, and a draft with no `##`
  headings is worked on as one part. Only Reshape may add headings, to divide such a draft
  into the kind of post's sections; restoring the opening's **Before the first pass** in
  History undoes that division as a whole, and the sections it added can be brought back on
  the Outline tab. A **Note for the whole draft** revises a draft with no headings as one
  part too.
- **Tone (optional)**, folded, starting from Settings.
- **Check facts against your sources (optional)**, folded: the same files, Google Docs,
  links and library posts as above, for Finishing's fact check. There is no research and
  no Length for a draft.

After **Start** nothing stops for you. The page says "Nothing needed from you", names the
step under way (researching, outlining, drafting) with one clock, and offers **Stop**, and
**Retry** if a step fails. The draft, or the outline for Shape, opens on the desk by
itself.

An interview's **Review outline and start a draft** and a saved blog's **Open writing
run** (when it has no step-by-step run) open this start too, with the outline or the saved
draft already in place.

## The writing desk

The desk is one page: the title, the opening, then a card for each section.

- **Edit in place.** Type in any card; it saves as you go.
- **Section notes.** Under each section, "How should this change?" and **Rewrite**. Only
  what the note asks for changes; the rest is kept word for word, at the same length and
  shape. With no note, **Write again** writes the section fresh from its brief, the
  sections before it and the sources.
- **Note for the whole draft.** One note ("tighten throughout") revises each written
  section in turn, with progress and Stop. A section that fails is named; the rest still
  go ahead.
- **Selection.** Select text to **Rephrase**, **Shorten**, **Expand**, **Fix** or
  **Ask…**. The result replaces the selection.
- **History.** Every rewrite, revision, restore and the first save of an editing session
  keeps the earlier text first, the last twenty for each part. **History** on a section,
  the title or the opening lists them, with a word-by-word comparison and **Restore**.
- **Outline.** The **Outline** tab renames, reorders, adds and removes sections (a
  removed one can be brought back) and edits each one's brief. **Write the draft** or
  **Write this section** works from it.
- **Sources and what needs you.** What the draft used, with **Add a source** at any time;
  later rewrites and the fact check read it. Anything the writer could not settle, such
  as a release date, is listed under **Needs you before publishing**, never in the prose.
- **Toolbar.** **Copy**, **Download**, **Google Doc**, **Mark as published** and
  **Finishing**.
- **Images.** An image in the draft, such as one a Google Doc brings, shows in the text as
  its short reference (`![][image1]`), with a thumbnail under the part that uses it. Keep
  the reference where the image belongs. The image itself is kept beside the draft, never
  sent to the assistant, and written back at the end of `DRAFT.md`, so **Copy**,
  **Download**, the Google Doc and the pre-publish check keep it. A rewrite that leaves a
  reference out has it put back where it was; one that changes or adds a reference has
  that taken out, and Finishing flags it. Each image can be up to 5 MB, and a draft's
  images up to 12 MB together; the 200,000-character limit counts the text only. An image
  the text names but that was lost (as an earlier rewrite could drop it) is found again in
  the part's History, the other parts' History, the original draft or the Google Doc it
  came from, without changing a word; one found nowhere shows **Image missing**.

One job works on a blog at a time; the desk shows it and offers Stop. An edit from a form
that is out of date is refused rather than written over newer text.

## Finishing

**Finishing** opens a side panel (a full-screen sheet on a phone). Every tool suggests;
nothing changes until you apply.

- **Humanize** at light, medium or strong: sentences that read as machine-written, each
  with a rewrite. Numbers, names, quotes and links are kept, and a rewrite that would
  change one is flagged.
- **Proofread**: dashes, words that often read as machine-written and repetition, checked
  at once, with **Fix** on each finding.
- **Check facts against sources**: each claim supported, not in your sources, or
  contradicted, with the passage, **Add a source** and **Keep it**.
- **Headline and opening**: alternatives to apply.
- **Feedback without a rewrite**: comments on shape, argument, audience and claims, each
  made a section note in one click.
- **Apply a voice**: the draft rewritten part by part in one of your
  [voice guides](#voice-guides), keeping its structure, facts, numbers, names, quotes and
  links. A part whose facts, code or shape changed is flagged.
- **Before publishing**: the pre-publish check, **Repurpose** (each copy becomes a new
  blog on the desk) and **Send to Google Doc** as suggestions, for a blog started from a
  Doc.

Each suggestion shows before and after side by side. **Apply**, **Edit** or **Skip** it,
or **Apply all** (flagged ones wait to be checked one by one). Each Apply keeps the
earlier text in History. Suggestions wait on this computer until you decide; only what
you apply is shared with a team.

## Start from a Google Doc

In **New blog**, choose **A draft**, then **Google Doc**. Paste the link or ID and choose
**Read Google Doc**. The page uses the workspace's remembered Google account, or the active
Google Cloud CLI account. Google Cloud CLI must already be installed and signed in with
Drive access; see [Google setup](google-docs.md#local-codex-and-claude-gcloud-setup).
Reading saves a private copy on this computer; it does not change the Doc, share it or
start an assistant. Check the text shown, then **Start**. The Doc stays linked, and
**Finishing → Before publishing → Send to Google Doc** later sends your changes back as
suggestions. A Doc that is already a blog here opens that blog instead of a second one.
Images are left out of the text; inspect them in the original Doc. Pending suggestions
stay in Google.

A blog edited in the manuscript editor (**Edit manuscript**) keeps its own Google tools:
selected suggestions or comments are previewed and sent only when you confirm. Its
**Polish another document** opens the polishing screen. The CLI remains available for Google
reconciliation and advanced operations.

## Your brand skill

Open **Settings → Brand skill**, as in Training Studio. A brand skill belongs to
your organisation and is supplied separately. You can write without one.

- **Its repository** takes an https or ssh address that Git can access with your
  existing sign-in. **Which release** takes a tag such as `v1.4.0`; leave it empty
  for the newest. **Check and save** reads release tags before saving anything.
  A failed check preserves the previous settings. Clear both fields to forget
  the repository; installed skills stay installed.
- **Use this brand skill** lists skills found in the usual shared install and
  assistant skill folders, following Training Studio's discovery rules.
  `BRAND_SKILL_RUNTIME` can point to a particular installed skill folder.
  Choose one and press **Use this skill**. The choice stays on this computer.
- **Install the brand skill** or **Install selected release** opens a sheet with
  the repository, tag and commit. Nothing is downloaded or installed until you
  choose **Install it now**. Only install from a repository you trust.
  Installation is refused while a blog is working and blocks new writing jobs until
  it finishes. Home and Status show its result. Use **Check and save** again to
  check for another release.

The install uses the release's own installer, with the same ZIP/checksum or
tag-clone protocol as Training Studio. It rechecks that the tag still points to
the commit shown. Research installation is skipped. If the release declares it
would install or replace another companion, Blog Studio refuses before running
the installer; install a compatible companion yourself first.

A blog run step by step (in chat, with `--brand ID --variant VARIANT`, or `--brand ''`
for none) takes a brand and variant from that skill; the shared `brand.brand` /
`brand.variant` default applies when the selected skill has it. The blog exports a
contract for the `blog` medium and keeps its exact naming and design guides with the
run. Blogs on the writing desk carry no brand contract. Existing blogs keep
that contract when settings or installed skills change, including when resumed
on another computer. Brand naming rules and visual guidance stay separate from
the author's voice; a logo or palette does not imply a company tone.

The brand repository, release and identity live in the shared settings file.
Installed skill paths and release-check observations stay in Blog Studio's local
data folder. Only the selected contract travels with a blog.

## Voice guides

A **voice guide** says how a piece should sound: a name and a page of text about register,
sentence length, openings and the words to use or avoid. **Voice guides** in the sidebar
lists them with a line from each. **New voice guide** runs in three steps: a name; then
**Write it**, or **From samples** with 3 to 20 posts, emails or notes pasted or uploaded
(Markdown, text, HTML or DOCX) and **Make the guide**, one job that reads only those samples;
then the guide's text to read and edit before **Save guide**. Samples are not added to the
library. Open a guide to edit its name and text or retire it. A guide is saved where voice
profiles always were (`profiles/`, or `.shared/voices` in a team workspace), so voices
learned before are listed as guides. On the desk, **Finishing → Apply a voice** rewrites a
draft in a guide; each part is previewed before and after, and you apply all, some or none.

A **kind of post** (a style) is the shape of a kind of writing, such as a product
announcement or a how-to: its parts, length and register. The start's first step chooses
one. **Kinds of post** opens from Settings, Home's Set up before you write, or Tools.
Blog Studio ships eight starters for tech-industry writing: product announcement, release
notes and changelog, technical deep dive, how-to and tutorial, point of view, customer
story, comparison and evaluation guide, and postmortem and lessons learned. A starter is
copied into your workspace only when you edit it, retire it or use it for a blog; you can
also export it. **Create a style** reads examples of a kind of writing by anyone, from
uploads, links or the library, and proposes a guide, which stays provisional until you
confirm it. **Write a style guide** is for one you write yourself.

### The older voice tools

Learning a voice from an author's posts, auditions, **Write as**, the default voice,
**Change the voice**, voice samples, LinkedIn imports and **Create voices for every author**
are off by default, while Blog Studio concentrates on writing well. **Settings → Advanced →
Show the older voice tools** turns them on; then the Kinds of post screen is **Voices and
styles** again and the rest of this section applies. Off, the page hides them, the server
refuses them ("Voices are switched off in Blog Studio settings.") and new blogs write with
their tone. Saved voices, samples and every blog's pinned voice stay as they are.

A **voice** is how one person sounds. A blog run step by step takes a voice and a kind of
post: the kind decides the structure, the voice the wording. Blogs on the desk write with
their tone and are pinned to no voice; **Apply a voice** with a voice guide is the desk's
way to sound like someone. Settings → **Voices and styles** opens the screen; from a blog,
**Tools → Voices and styles** opens the same list where a voice can be applied.

**Write as**, on **Interview me**, offers your default voice, another saved voice, no
particular voice (the tone you describe), or **Learn a new voice…**. Your personal default
voice (**Settings → Default voice**) is pinned at the revision it names. **Change the
voice** on a step-by-step blog switches its voice for what comes next; it asks once when
the blog already has writing, since its reviews will need a new look. Nothing is
rewritten, and the blog's history records the change.

A voice belongs to one author, and that author need not be you. If you ghostwrite, learn
a voice for each person you write for, from their published posts. Each voice sample
records whose writing it is, and the sheets ask before reading anything.

There are two ways to learn voices.

**Create a voice** makes one author's voice in one sheet, in order: name the author, add
their writing, tick up to twenty samples, confirm you may analyze them, and build.
Everything you add lands in the same list of samples, ticked, from any of:

- **Upload their posts**: several files at once, each saved as that author's sample.
- **Posts already in the library**, narrowed to this author and to posts with no
  author; **Use as a sample** makes one a voice sample, with the author named.
- **Import a LinkedIn export.** On LinkedIn, open Settings & Privacy, Data privacy,
  then Get a copy of your data; choose Profile and Articles and wait for the email.
  Choose the downloaded zip in the sheet. Only `Profile.csv` and the articles are
  read: the person's name becomes the author, their headline and About text become
  author background, and each article a voice sample. An export is usually your own;
  when a colleague hands you theirs, give their name in the sheet. Nothing signs in
  to LinkedIn, and connections or messages are never read.
- **Add links to posts.** Paste links, or choose a text file with one link per line;
  the author is suggested from the file name and you can change it. Blog Studio first
  shows what it will do: the site, the links already in your library and the ones it
  will fetch. It then reads each new page once, in batches, and saves it in your
  reference library under "Published posts by" the author. A post whose byline names
  someone else is left out unless you keep it; a kept post keeps its published byline.
  Failed links can be tried again without fetching the rest. LinkedIn pages cannot be
  read this way; use the export.

**Create a style** has the same shape, with **Add links to examples** in place of the
byline check. From a terminal, `library voice-links` does the same work; see
[commands](commands.md). **Write a voice guide** and **Write a style guide** stay beside
them for a guide you write yourself.

**Create voices for every author** is for a whole team library at once. It lists every
author whose posts are in the library, by exact name ("Dan" and "Dan Smith" are two
people), with their post count, up to 100 ticked in one batch. A name that could be a
fuller one ("Dan" beside "Dan Smith", or a voice named "Dan Baskette") shows "Might be the
same person as …": **Same person as** names that author's posts by the fuller name once you
confirm, and **Different person** stops the suggestion. Each post's author can also be
changed in its **Review details**. An author with two or more
readable posts is ticked; one with fewer is listed, unticked, with the reason; one who
already has a voice is shown as **Update** their voice and gets a new provisional
revision of it rather than a second voice. Every ticked author is checked before anything is marked or queued, so a
refusal for one changes nothing. One permission confirms the batch, and one
learning job per ticked author joins the queue, each reading up to twenty of the
author's posts, newest first, which then become their voice samples. The sheet follows
each job; **Review** opens a ready voice to save as provisional or confirm. It is offered
on the Voices and styles screen, the Team library and the result of **Add to library**.

Every sample is a source in your reference library, so it follows the same sharing rules
as any other source. Learned voices and styles stay provisional until you confirm them,
and an existing blog keeps the revision it was started with.

## Blogs started step by step

Blogs started before the writing desk, and guided blogs run in chat, keep their
step-by-step path: research (when chosen), outline, draft, review and a handoff, each made
by your assistant and brought back for a decision where the blog's review level says. A
finished one offers **Open on the desk** on its Done card, which Home's **Finished
drafts**, **Blogs** and the manuscript editor all open; it brings the manuscript onto the
desk, including edits made since in the editor, and the run stays readable as it ended.

Research in a run reads **your documents** (its selected sources), **your sites** (the list
in Marketing Studio's Shared settings, or a site added for that blog only) and/or **the
public web**. Your sites are searched with the assistant's web search, and only pages under
them are saved. That check is Harness Research's, so without it (see Status) your sites
alone are refused. The runner uses your CLI account, with a time limit for each step. It
does not hold an API key and has no spending limit; your account's usage charges or limits
still apply.

| It makes | You decide |
| --- | --- |
| Research questions, when research is chosen | Are these the right questions? |
| Research findings | Is the evidence sufficient? What is still unknown? |
| An outline | Is this the argument you want? |
| A draft | Does it say what you mean, in your voice? |
| A review | Which findings need changes? |
| The handoff | Are the title, excerpt and links ready to hand over? |

A run keeps the review level it started with; **Settings → Where new work stops** sets the
level for runs started from now on, in every studio, saved at once. One
line under a run's stages says how many steps are left, where it next stops and what
its jobs have cost so far. **Ask for changes** says what is drawn again and what those
steps took the last time they ran. The default, **Balanced**, stops for you
twice: at the outline, with the research questions and findings beside it, and
at the run's last step (the handoff or your chosen stop), with the steps
since the outline beside it. The steps between continue on their own; Blog Studio
records that the review level accepted them, never that you approved them.
**Step by step** stops at every row, and **Automatic draft** only at the last
step. Without an outline, as when revising a draft, Balanced also stops only at
the last step.

Choose an earlier stage under **Ask for changes** to revise the draft or outline
after reviewing it, including one the review level accepted. The assistant edits
that saved document, changing only what you asked. The later stages are made
again and reach you at their usual stops. You can stop at outline, draft or
review instead of making a package. Review mode keeps the manuscript as written;
revision makes a new draft while retaining the original.

**Blogs** shows every blog, on the desk or step by step, and saved writing. Each card has **Delete**, as
each blog in Home's lists does, which asks for the blog's title, stops anything running for it and keeps it for
30 days under **Recently deleted**, where **Restore** brings it back. Open a run
to see steps and made files. Each review page renders the saved Markdown as a
paper document, with **Checked for you**, **Worth a look** and **What changed**
alongside it.
Comparisons use the exact last approved version. **Approve** opens a confirmation
sheet; **Ask for changes** lets you select an earlier stage. A finished or
paused run returns to **Resume** when you request a revision. A changed version
stays separate from the document you are reading until you choose to reload it.
The editorial pipeline, library, findings and memory tools remain available under
**Library and team tools** on Blogs.

## The Team library

**Blogs → Library and team tools → Team library** lists every item your team writes
from. Its toolbar holds one action, **Add to library**: files, a text file of links or
pasted links, and a Google Doc, with each post's text, title, author and date read and
kept. **Each post's own author** is the default, read from each page's byline; one typed
author and no author remain choices. Under **More ways to add**, **Import a blog or site**
previews a whole folder, website, feed, sitemap or export, and **Upload one file**
summarizes and tags a file or starts an editable blog from it.

Filters sit in one row (search, role, kind of post, author, status), with the collection
under **More filters**; on a phone, **Filters** opens them. Tick rows, or **Select all on
this page**; the selection bar then appears with **Select all N matching**, which ticks
every item the filters match, through the server, up to 500 in a selection. Ticks stay as you page and change the
filters, and the bar says how many are out of view. The bar's actions learn a style or a
voice from the ticked items (up to twenty are read) or start a blog with them as
examples (up to fifty). **Clear** empties the selection.

Assistant notes are its judgment, not proof of completed checks. Public source
links and quoted claims need review: the browser runner does not independently
fetch and validate every citation. An approved review does not mark all existing
Blog Studio factual checks as passed.

**Pause after this step** lets the current job finish and prevents another.
**Stop** ends its process. Failed jobs retain previous writing and offer
**Try again**, which makes that step again in a new job. No job approves its own
result or publishes a blog. **Finish**, at the last step, always opens its
confirmation, whatever the review level: it approves the shown version and keeps
the draft in the team library as a reference and an example of its kind of post.

A stopped run says what to do next beside the error:

- **A CLI failure** names **Status → Check this computer** and offers **Open
  Status**, including for an assistant that is not installed or cannot start.
  **What the assistant said** shows the last 20 lines its command printed, redacted
  and without any line that echoes the job it was given, kept in
  `.blog-runs/diagnostics/cli` on this computer only, and replaced by the next job.
- **A step out of time** says it ran out of the time a step may take, with this
  blog's minutes. The limit is in **Settings → Step time limit** for new blogs;
  **Try again with more time** doubles it for this one.
- **Research** says its round while it works ("Round 2 of 3, the independent
  check"); each job's seconds are kept with the run on this computer, and its tokens and cost where
  the CLI reports them (Claude Code does; Codex, as Blog Studio runs it, does not).
  Research that stops before its check accepts it is kept in the blog's
  `.studio-research-draft` folder, which the Team Hub skips and a shared studios
  repository ignores. It is used only while the blog's inputs and research version
  are the ones it was made for; research saved any other way lets it go. A refusal lists **What the research check objected to**,
  grouped by kind and verdict with the first note of each. **Try again** continues
  from the kept draft for up to three more rounds, within the step's limit, and says
  what the last attempt took. **Continue without research** takes the research steps
  out of the run, with a confirmation; the outline and later steps then work from the
  brief and selected sources alone.

First-run setup opens **Writing preferences**, and an assistant that is not
installed is marked "Not installed — see Status" there.
One job works at a time in this workspace. Models can search the web only in a
public research job; they have no shell, file tools, connected apps or approval
tools. Only the runner saves their returned documents.

## In a conversation

Say **“Use Blog Studio. Make a guided blog about [topic], with approvals.”**
Your assistant asks for the brief, selected sources and voice, then makes each
stage and waits for your decision. Short requests such as “proofread this” keep
their existing focused workflow.

You can start in either place. **Run this from here** moves a conversation run
to the page. **Continue in the conversation** stops its browser worker and gives
you a request to paste into your assistant. The same files and decisions stay in use.
For a saved blog with no run, its details' **Open writing run** brings its draft to the
desk start.

## Shared studios repository

Join from **Settings** or **Status**. The page switches to its own team clone.
Blogs have one driver, with **Take this blog**, **Take over**, **Hand over**, and
**Record in team repository** controls. **Share now** retries pending decisions.
See [team workspaces and migration](team-workspace.md) and the
[shared studios settings](shared-studios.md). Settings saves shared values to
that file directly, with no local override or additional consent toggle. Missing
or unreadable shared settings use built-in defaults; writing remains available.
Legacy local copies migrate only to missing shared members, then are removed.
An existing shared value is kept and reported. An unreadable file is preserved
and shared-value saves are refused until it can be read.

## Saved work and teams

A desk blog keeps its draft in `desk/draft.json` (the title, the opening, each section
with its brief, and each image's label and alt text), its images' data in
`desk/images.json`, and earlier versions in `desk/versions/`, and rewrites `DRAFT.md` on every
save so Copy, Download, Google Docs and the pre-publish check read the same text. A draft
saved in chat, restored from its history or accepted from Google comes onto the desk as a
new version of each part it changes, so the next desk save keeps it.
Suggestions from Finishing wait in `.blog-runs/desk-proposals/` on this computer until you
decide. For a run, outlines and drafts remain `OUTLINE.md` and `DRAFT.md`. Research questions,
research findings, review and package live under `derived/`. The stage record
is `derived/blog-run.json`; earlier writing and decisions remain in history.
Changing an input or an approved document invalidates affected decisions.
An old page cannot approve a newer version. If someone edits while a worker is
running, that edit is kept and its late result is refused.
An edited saved document is never regenerated automatically. Choose **Review
this saved version** to bring your edit back for approval, ask for changes, or
continue in chat.

Runs use the existing selected Team Hub and its ordinary save, offline queue,
retry and conflict protections. Execution controls stay local and never travel
through the Hub. A checked-out run on another computer starts paused until a
person resumes it. There is no cross-computer runner ownership lease: run a
given blog on one computer at a time and reconcile competing revisions in chat.
Read-only Hub users can browse runs; page mutations recheck write access.

Google Docs imports and selected suggestions/comments are available on the page;
advanced pushes, pulls and reconciliation retain their existing explicit chat commands. The package is a Markdown publication handoff, not a Google
transfer or a publishing action. The page does not change Google sharing.

## Verification

[Runner validation](runner-validation.md) records the state matrix, synthetic
checks and acceptance limits. [Hub acceptance](hub-acceptance.md) covers the
existing create/join, intake, saves, reviews and cross-clone protections.

## Research stops and supplied material

This section is about blogs run step by step. Runs that research your documents only, with selected facts/material, map the claims in that material
instead of running research. Each claim names a source ID and an exact passage. The runner
checks words against that source (ignoring whitespace and line breaks), allows one
correction and stops on another failure. Later writers receive the map and keep the
claims within what the material says. Balanced and Automatic continue to the outline;
Step by step reviews the map. Continue without research drops this stage too.
From-files runs with your documents only remain unchanged: their files are read at every stage.

Research from your sites or the public web uses a separate tool-less plan with at most eight questions, investigated
together and checked independently. The research review leads with the authored brief,
checker's note, gaps, source limitations and findings mapped to questions. Report and
evidence are folded below. Ask for changes says before sending that the full research
runs again, what its last try recorded and which saved later stages it will make again.
Saved older runs continue through their original research pipeline: supplied-only reads
as your documents, web-allowed as your documents and the public web.

Source discovery searches your sites first, with `site:` queries, and uses the wider web
only for gaps when the public web is ticked too. Every page and every redirect is checked
before it is saved: with your sites and not the public web, only pages under a listed
site (its own host, its path or one below it) are saved, and the rest become source limits
that name the sites. Private and local addresses are refused whatever is ticked. The
research review and a refusal say how many pages were outside your sites.
