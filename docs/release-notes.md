# Marketing Studio 4.5.0

Marketing Studio 4.5.0 ships Blog Studio 4.7.0, Presentation Studio 4.5.0 and Training Studio 4.5.0, with Harness Research 1.0.1 pinned and Tanzu Brand 0.14.1 tested. These are the changes since 4.0.0.

- **Your team's repository, connected.** Home says where each studio's work lives: connected to a repository and branch, local Git on this computer, or not connected, with a **Connect** action. A shared repository set in Marketing Studio now reaches studios that already have a workspace.
- **One team library.** Blog Studio keeps finished blogs, added files, lists of links and Google Docs in one library, each with a role, an author and a kind of post. A list of links by many authors is sorted by each post's own byline.
- **Voices and styles.** Learn a voice for any author, so ghostwriting has one voice for each person, and start from eight ready-made styles for technical writing. A voice can be learned from a file of links to an author's posts, from up to twenty samples. Voices and styles opens from Blog Studio's Home and sidebar.
- **Say what each file is for.** Each upload is marked as facts, an example of the kind of post, or approved messaging. Examples shape a post but never supply its facts. **I know the point** starts from the point you already have, and you choose the voice as you go. Write from a brief takes every file at once, and a Google Doc is read tab by tab.
- **The authoring workflow review, Phases 1 to 5.** Research can finish, and a failure says what to do next. Each thing has one name, and **Where this run stops** sets how often a run stops for you, saved once for every studio. Research stops show the brief, the independent check, the gaps and the findings for each question, along with what a change would cost. A training, deck or blog can be finished on its page: download it, bring back your edits, apply review findings and approve the version shown. Harness Slides, Harness Research and the brand skill are now fully used.
- **Research checks read the originals.** The independent check reads a supplied Google Doc, PDF or Word file as it is, so supplied material no longer fails the check again and again.
- **Research from your documents, your sites and/or the public web**, in every studio. Your sites are listed in Shared settings. Each page research saves is checked against them, redirects included, and a site can be added for a single piece of work.
- **Announcements that read like announcements.** Blog Studio writes approved messaging in the product's own voice and keeps source notes and open questions out of the text.
- **Delete from the lists.** Decks, trainings and blogs can be deleted from the lists and Home cards that show them, with each studio's usual confirmation.
- **Also since 4.0.0:** one shared Golden Gate look on every studio page; `marketing-studio start`, `stop` and `restart`; installer diagnostics and repository sync; slide text you can change after a deck is built; blogs finished, published, deleted and restored from the page; a blog written from your uploaded files, with three angles to pick from; and pages that work better on a phone.
- **Companions.** Installs use Harness Research 1.0.1 and Harness Slides 0.16.0, each at an exact commit and source checksum. Decks need a brand skill at 0.14.0 or newer, and this release was tested with Tanzu Brand 0.14.1. Marketing Studio never installs the brand skill.

Download `marketing-studio-installer.zip` for the whole suite, or one studio's installer ZIP. Each has a `.sha256` file for checking the download. Unzip it, then run `bash install.sh` in the unpacked folder, or open `installer/Install Marketing Studio.command` on macOS. Close running studios before you update. Your existing workspaces and settings are kept.

Signing in to an assistant, your organisation's brands and fonts, and optional Google setup are still your choices. Installing starts no provider job.

## Unreleased: the Document Library, existing work and Blog Studio updates

- **Add existing work to library.** Marketing Studio's **Library** screen can now
  bring in work kept before the library existed. **Preview existing work** reads
  only the workspace each studio remembers on this computer. It lists each
  workspace, every item with its type and formats, and what is missing, such as
  **no PDF** or **needs text**. Nothing is added until you press **Add N to
  library**. No other folder is searched, no studio is started, and nothing in a
  workspace is moved or changed. Adding again adds nothing new, and a newer revision
  in the studio adds a library revision. If anything changed since the preview,
  nothing is added and you preview again.
- **Blog Studio's team library comes along.** Finished blogs, uploads, links,
  Google Docs, imported posts and voice or style samples are offered from it. A
  finished blog keeps the library document that finishing it again later would use.
  Each item's Blog Studio ID, revision, roles, kind of post, author, voice and style
  are recorded with it. Files kept for one blog only, Team Hub snapshots, retired
  items and items only in the Team Hub are left out, and the preview says so. The Team Hub is never changed. Adding existing
  work from Presentation Studio, Training Studio and Infographic Studio is not
  offered yet.
- **Update available in Blog Studio.** A desk source taken from the Document Library
  says which revision the blog reads. When the library has a newer one, the desk
  shows **Update available** and **Use revision N**. Only that button takes it:
  later rewrites read the new revision, nothing already written changes, and the
  earlier revision stays readable. It waits while a desk job works on the blog.
- **Keep in library when uploading in Blog Studio.** Uploading files on the desk
  start or under **Add a source** offers **Keep in library** (the default) or **Only
  this blog**. Keep in library also keeps a copy of each file, with its readable
  Markdown, in the Document Library on this computer. It never changes how the file
  is shared, and a library problem is shown on the file's row without stopping the
  upload. Links and Google Docs stay with the blog. The same file uploaded again is
  kept once, and Add existing work shows it as already in the library. The team
  library's own Upload and voice or style samples don't offer the choice: they feed
  the team library and voice learning, not one blog's sources.
- **Checked in a browser.** The Library screen, Add existing work and the **Add from
  library** sheet are checked at desktop and phone widths, in light and dark, and
  with reduced motion and reduced transparency. On a phone, a ticked document's
  title in the sheet now wraps instead of running past the list.

## Unreleased: the shared Document Library, first slice

- **One library for every studio.** Marketing Studio has a new **Library** screen.
  Add text, Markdown, HTML, Word or PDF files once. Each is kept as it was sent,
  with its readable text as Markdown. Browse with search, **Type** and **From**,
  and **More filters** for origin, status and author. You can preview the Markdown
  and download the Markdown or the original.
- **Finished work is kept there too.** A finished or published blog is kept as
  Markdown. A delivered Presentation Studio deck is kept as its slide-ordered outline
  Markdown. Delivering or finishing again adds a revision only when the text
  changed. A delivered deck also keeps its PDF: the one Harness Slides rendered of
  that exact deck when it was last previewed, kept only when it still matches.
  Its entry then says **PDF saved**. Otherwise it says **PDF needs export** and
  why, and no PDF is claimed. If the library save fails, the deck says so and
  offers **Keep in library again**, which delivers and renders nothing again.
- **Keep in library, or Only this project.** A file added on Presentation
  Studio's desk is kept in the library too, unless you choose **Only this
  project**. The deck has its own copy either way, and nothing is shared.
- **Add from library, for one project.** Presentation Studio's desk Sources card
  and Blog Studio's sources card each have **Add from library**. Ticks stay when you
  page or filter, **Select all on this page** and **Select all matching** are
  bounded, and an unreadable document cannot be ticked and says why. **Cancel**
  changes nothing.
- **What a project keeps.** Each chosen revision is copied into the project, which
  keeps working if the library later changes or is gone. When a newer revision is
  available, a deck shows it and takes it only with **Use revision N**. In Blog Studio
  you choose a role for each document: facts, approved messaging or an example. An
  example never becomes evidence, and the documents stay with that blog only.
- **Nothing starts by itself.** Choosing context starts no research, grants no web
  access and sends nothing to an assistant. A remembered filter is never a
  selection, and a new project starts with no documents chosen.
- **Local.** The library lives in `library/` under your work folder (normally
  `~/Studios/library`). Its location is saved the first time you use it, and it
  doesn't move if the work folder changes later. Nothing in it is shared with your
  team or the Team Hub.

## Unreleased: shorter shared setup, clear ownership and readiness

- **Four everyday choices first.** Shared settings leads with you and your assistant,
  your workspace, brand, and delivery, with section links. Models and reasoning, the brand
  skill release, research sites and studio installations are named **Advanced** parts that
  say what they hold, and tag an **Override**, while closed. First-run setup asks only the
  everyday choices.
- **A visible save state.** All changes saved, Unsaved changes, Saving… and Saved at a time
  stay in view with Save settings. Typed changes survive moving between views, a reload
  asks first, and a refused save keeps them. Overrides, values the page does not show and
  the outdated-form checks are unchanged.
- **Who owns a value.** Shared, Override and Project tags say where each value is set.
  Presentation Studio's and Training Studio's Settings say which values are shared, which
  each deck or training keeps, and which are the studio's own, with Change shared settings.
- **Readiness in words.** Each studio card says **Can open**, **Needs setup**, **Not
  checked** or **Not installed** on the card, not only in a tooltip, with one recovery
  action. The home separates launch prerequisites, the on-request computer check and
  account checks that each studio makes when a task needs them. Browsing and checking
  start no assistant, sign-in, installation, workspace preparation or paid work, and model
  lists load only when Models and reasoning is opened.

## Unreleased: Infographic Studio visual editor and history

- **Edit words beside the page.** The preview stays beside an Edit words panel. Choose
  an element by name (Page heading, Section 2 heading, Section 1, step 3 label) or select
  it on the page, where it is outlined and its place described. Element IDs move under
  Advanced. Saving keeps the selected element, focus and scroll, so two headings can be
  edited one after the other.
- **Which revision is which.** Current work, the rendered preview and the last approved
  delivery are shown separately. A save confirms its new revision, says when the preview
  is out of date and offers Update preview. Unsaved words are kept for each infographic
  and element in the tab, across a reload, another infographic and a refused save.
- **History in words.** Each revision says what it did, what it changed and when, beside
  its number and exact identity. Saved files keep every rendered revision's downloads;
  approved files never change, and edits and restores never carry an approval over.
  Home shows each infographic's working state with its revision.

## Unreleased: Infographic Studio review to delivery

- **One route and one next action.** Where this stands shows Story, Draft page, Review
  and checks and Approved delivery with the current step, and says what is complete,
  what needs you and what you can download. The toolbar offers that one next action.
- **Review, checks and approval, each explained.** Recording your review of the actual
  page runs the local checks straight after. Assistant inspection is optional and
  separate. Approve revision N and prepare files approves that exact revision and then
  prepares its files on this computer in the same action, so an approved page is never
  shown as a new draft. If files cannot be prepared, the approval is kept and Prepare
  approved files retries locally.
- **A receipt for every format.** Delivering a Google Doc and PDF lists both, each with
  its revision and Open or Download action. Partial success is shown honestly: what
  succeeded is kept, retrying the PDF sends nothing to Google, and an unconfirmed Google
  Doc is only checked again, never resent.
- Exact-revision checks, explicit approval, image recovery and spend protection are
  unchanged.

## Unreleased: Infographic Studio Team library first use

- **A setup state, not an error.** With no shared repository, Team library says so
  and offers **Configure shared repository**, which opens Shared settings at Your
  workspace. Saving or choosing Back returns to the same infographic and reopens the
  library; connecting is still your choice.
- **Connection state.** A configured library shows its repository, branch, whether it
  is connected and when it last synced, read locally so an offline copy still lists.
  A commit that has not reached the team repository is counted with **Retry pending team
  push**.
- **Recovery that says what to do.** Refused access, a missing repository or branch and
  an unreachable host each name a recovery step without repeating Git's output or any
  credential. A failed first connection no longer stops the library from opening.
- Opening or configuring the library shares nothing. Shared settings keep their single
  locked file and outdated-form checks.

## Unreleased: Infographic Studio Codex image outcomes

Infographic Studio's Codex image adapter now reports each failure from the worker's
own diagnostics rather than from anything the model wrote. A turn that fails after a
successful exit is no longer collected as artwork. A saved file that is not a usable
PNG is reported as an invalid image, separately from a Codex that cannot offer its
image tool. Sign-in, usage limits, invalid images and an unavailable image tool each
say what to do next. Nothing is retried, and live generation and editing remain a
separate acceptance step.

## Unreleased: Training Studio standing on every screen

A training made on the desk now has one standing that Home, Trainings, Status and the desk
all read: working on its own, needs your decision, needs attention, drafts to mark ready,
ready, or stopped. A finished writing job with a retained review finding is listed under
Needs you with a button straight to its level, material and slide, and is never called
Finished. Status counts drafts still to write apart from drafts to review and mark ready
and what needs attention. A deck whose slide text waits says Needs your text approval, and
materials nothing is writing say Not written yet. Saved runs keep their own words, and
reading any screen starts no work. A desk training whose drafts are all written but not yet
marked ready now sits under Needs you, existing ones included, and is told once rather than
again after each Mark ready.

## Unreleased: Training Studio material review

A material on the Training Studio desk opens to read, as learners receive it, with its
formatting rendered and its teaching details folded away; **Edit** opens its parts, and text
not saved yet keeps it open across tabs and levels. Copy text copies a section's exact saved
text. Finishing opens on the material in front of you, with All materials for another. The
toolbar's download says it is the level's, and each material's own is on its card. While a
deck's slide text waits for approval, the desk opens on that deck with no editor beside it.

## Unreleased: Training Studio Google Doc after local creation

A training made on the Training Studio desk with local copies only can make a Google Doc
of a guide or brief later, from Google Doc on the desk. The sheet names the material, the
version and the Doc it makes; the one explicit action sends exactly that version and gives
its link. Nothing is marked ready, no job starts, the file is kept, and the training is not
switched to Google Docs, so Ready still sends nothing by itself. Update the Google Doc
sends a newer version to the same Doc and never writes over changes made in Google;
those can be brought in, or a new Doc made beside the edited one. After
an uncertain answer from Google, another Doc is made only when you choose Make the Doc
anyway. Trainings started with Google Docs keep updating them as they are marked Ready.

## Unreleased: research citation handoffs

Research workers are explicitly told which saved source IDs to cite. If a worker
uses its tool's source handle while naming that same source differently in its
dossier, the shared adapter reconciles the ID only when the capture's file,
origin and permission identify exactly one dossier source. Claims and quotations
are unchanged and still pass the pinned Harness Research checks and independent
review. Missing or ambiguous references are refused inside the current job with
the fact, citation field and available IDs, rather than a generic unknown-source
message. Existing training state, source permissions and helper versions are kept.

## Unreleased: Infographic Studio 0.1.0

Adds the fourth independent editing desk for supplied text, Markdown and selected
CSV: source-backed story choices, six one-page forms, explicit brand snapshots,
Codex/Gemini image adapters, precise art direction and reference edits, actual-pixel
review, focused copy/story edits, immutable history/restore, exact user approval and
PNG/PDF/editable SVG/accessible-text delivery. Marketing Studio adds shared setup,
native discovery, lifecycle/CLI flags and protected phone/LAN launch.

The pipeline uses Python's standard library and no frontend build or image SDK.
Infographic Studio-only packages omit Research/Slides companions; unrelated subsets
omit its renderer. Its initial acceptance target is macOS ARM64. Live generation,
reference editing and inspection for both provider routes, owner illustration
acceptance and publication remain separate gates. See the
[release acceptance checklist](../studios/infographic/docs/acceptance.md).

## Unreleased: Infographic Studio 0.2.0

Adds previewed Word/PDF/HTML and multi-file intake, explicit Google Doc/public-page
capture, complete reviewed Harness Research imports, selected cross-studio material,
and optional team inventories with driver takeover/handover. Delivery offers the
exact local PDF, a new Google Doc, or both. Google Docs contain the approved page
image plus editable accessible text/source notes; the original Doc is kept. Unknown
uploads reconcile read-only. Private sources and artwork need explicit sharing
selection, and prompts/jobs are excluded. Phone uploads retain bounded route limits.

Python 3.11+ and standard-library application code remain the baseline, with no
frontend build or document/image SDK. PDF extraction and Google access use explicitly
installed optional tools. Real Google conversion fidelity, both live image-provider
routes and owner illustration sign-off remain separate from offline success. See
[first-release readiness](infographic-first-release-readiness.md) before publishing.


### Google intake and home readiness corrections

Infographic Studio Google intake now accepts Docs and Slides links using the existing
default Google sign-in, without a repeated account form. Captured Slides text includes
tables and speaker notes; unread visual material is shown as a coverage gap. Delivery
uses Marketing Studio’s shared output default. The home screen separates **Ready to
open** from **Running**, refreshes status while visible and on return, preserves unsaved
settings, and clears stale green indicators when the server cannot be reached. Local
readiness never claims provider sign-in or successful generation.
