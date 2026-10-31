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
