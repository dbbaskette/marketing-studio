# Infographic Studio

Turn supplied information into one clear page. Paste notes, upload text/Markdown/PDF/Word/HTML files or selected CSV,
read a Google Doc or public HTTPS page, or import selected studio material; choose a story; build and inspect the
page; make focused edits; approve the exact revision and download PNG, one-page
PDF, editable SVG and accessible text. Explanatory artwork stays raster inside
SVG; labels and chart marks remain editable.

The first release implements qualitative and measured comparison, process, timeline,
number callouts, component and measured parts-to-whole explanations, and conceptual explanations in A4, US Letter and 1080 × 1350 digital
portrait. Remote reads, reviewed research imports and selected team sharing are explicit actions.
The app does not start public research or OCR implicitly. Sources and generated files
stay in the local workspace; connecting the team repository keeps an independent private clone.

## Start

Use Marketing Studio's Infographic Studio card, `marketing-studio open infographic`,
or `marketing-studio start --is --lan` for an explicitly enabled trusted phone/LAN
session. Native launch and setup also work independently:

```sh
python3 runner/studio.py status
python3 runner/studio.py serve --open
```

A missing shared configuration opens the same shared setup used by the other
studios. Finishing setup or launching explicitly creates a missing local workspace;
existing workspaces are preserved. Shared assistant, model, effort and brand choices
remain authoritative. Infographic Studio keeps its local workspace even when other studios use a team
repository. **Team repository** → Connect or sync explicitly clones the configured repository;
only **Share to team repository** commits and pushes a reviewed inventory.
The native **Settings** screen opens shared setup, says what is ready on this computer (and
that the assistant and image provider are checked the first time they are used), keeps
**Team Git email** with the team repository, and holds the image and renderer defaults.

Long assistant work belongs to its infographic: while it runs, only that infographic's
conflicting controls wait. The sidebar, Home, Settings and other infographics stay usable,
Home's card says what the infographic is doing, and **Stop waiting** leaves the work
running on this computer; coming back shows its progress or result, and nothing is
requested again. A reload returns to the same infographic, place and open sections.
Problems appear once, beside the field or in a notice above the page with **Dismiss**;
confirmations leave by themselves.

Python 3.11+, Git and a compatible headless Chromium renderer are required. Prepared
supported-platform packages include private Python, Node and a checksum-pinned
renderer. Node supports installed brand add-ons; the Infographic Studio pipeline
uses Python's standard library, no frontend build, no image SDK, and no required Research or Slides runtime.
Optional reviewed research import uses an explicitly installed schema-2 Harness Research helper. A separately installed brand add-on may have its own prerequisites:
the current Tanzu Brand shared-contract exporter requires Harness Slides 0.14.1+.
Nothing installs or updates those prerequisites automatically. A supplied resolved
brand contract can be adopted directly with the native `brand` command.

## Provider choices and usage

- **Codex:** uses the shared Codex model/effort and existing Codex sign-in. The native
  image adapter enables only the built-in image generation path; other text workers
  retain their existing confinement. No separate OpenAI image API key or fallback is
  requested. Image availability and account access remain unverified until a live run.
- **Claude Code + Gemini:** Claude Code plans and inspects; Gemini generates and edits
  images through the documented Interactions API. Set an image-capable Gemini model in
  native Settings. Generation requests PNG at 2K with a portrait aspect ratio, without
  search/tools or stored interaction history. The selected model must support those
  options; no silent downgrade or provider fallback occurs.

Set `GEMINI_API_KEY` only in the environment of the server process you explicitly
launch. For a terminal launch, export it in that terminal before launching the app.
For a desktop launch, use a launch environment you control that supplies the key;
a desktop app does not inherit an arbitrary terminal's exports. Do not paste keys
into shared settings, source material, prompts or an issue. Image API usage is
separate from Claude Code usage; Codex uses its existing account allowance. Only
reported token/cost data is shown; unknown prices are not estimated.

Assistant work starts only after an explicit action. Building an illustrated page
can use planning and image allowances; review the disclosure before starting it.
Long page operations show a persistent activity notice with the real current step
and elapsed time, including inside an open dialog. Refreshing the same tab restores
an active operation's notice. If the POST connection is lost, the page checks status
without repeating the request. A second long operation on that infographic is
refused while the first is active. Source previews also show immediate activity.
These notices describe the current server session; restarting the server clears
them. Saved projects and durable image/Google recovery records remain authoritative.
Planning has a five-minute worker limit. Its errors distinguish timeout, sign-in,
usage limits, unavailable models and invalid output. A timeout ends and collects
the owned worker before offering an explicit retry; no retry starts automatically.
The proposal selects at most 12 source-backed facts for one page. Exact quotations
are located by the application, rather than asking the assistant to count character
offsets. Codex planning uses the CLI's [JSON output schema](https://learn.chatgpt.com/docs/developer-commands#codex-exec);
native evidence, calculation and story validation still decide what can be saved.
The shared model and reasoning settings are preserved.
Codex art direction and actual-page inspection also use bounded JSON response
schemas with the page's owned region and asset IDs. Native content, reference,
complete-inspection and approval checks remain authoritative.
Generated paraphrases stay in the assertion field; their literal value is taken
from uniquely located captured evidence. Whitespace and quotation typography can
be matched while retaining the original source offsets. Exact numeric strings
become numeric values only when backed by their source or a checked calculation;
source display precision and measurement context remain visible.
Planning responses are retained privately against their source and brief revision.
If validation needs attention, **Check saved proposal** rechecks that response
locally, without another assistant request. **Review source material** opens the
captured text; **Ask for a new plan** explicitly starts a fresh request. Changing
the source or brief invalidates the saved response. Raw planning records are never
included in a team sharing inventory.
Descriptive comparisons and component explanations do not need measurements or a
numeric scale. Generated plans keep fully checked useful alternatives when another
option is unsupported, without repeating the assistant request. Explicit numeric
charts still require actual, comparable source measurements.
Process step numbering is structural; additional numeric claims still require
evidence. All-zero measurements retain zero labels and zero-length marks. A page
build tries the supported arrangements before asking you to prioritize content;
it does not drop text or reduce the readable type floors.
Actual-page inspection uses the selected assistant's multimodal path, or you can
record your own review after viewing the current PNG at intended size. CLI help
and capability discovery are not proof of account access or successful generation.

## Editing and recovery

The desk exposes direct copy edits, a named-block or whole-story revision, a precise
saved image brief, reference-guided artwork edits, pixel inspection, findings,
comparison, history, restore and all four downloads. Earlier deliveries are labeled
when they no longer match current content.

The visual editor keeps the page preview beside **Edit words**. Choose an element by
its name (Page heading, Section 2 heading, Section 1, step 3 label) or select it on the
page; it is outlined on the preview and its place is described. Element IDs are under
Advanced. Saving keeps the element, focus and scroll position, confirms the new revision
and says whether the preview is out of date, with **Update preview**. Unsaved words are
kept for each infographic and element in that browser tab, including across a reload,
opening another infographic and a refused save. Saving unchanged words makes no revision. Three states stay distinct: current work, the rendered preview and the last
approved delivery. **Saved files** keeps every rendered revision's downloads; approved
files never change. **History** says what each revision did (for example Edited words,
Ran checks, Approved this exact revision, Restored an earlier revision), what it
changed and when, beside its revision number and exact identity. Home shows each
infographic's working state with its revision. Required content, locked wording, located
facts, exact calculations, readable fit and actual fonts are checked. Unknown units,
periods or denominators block quantitative comparisons rather than being invented.
Print body/source floors are 12/9 pt; digital floors are 24/18 px. A selected brand
can raise them. Missing or unlicensed fonts require explicit user action; no font
binaries are redistributed. Other computers need compatible fonts to edit SVG.

Image intent is durable before a provider call. Reopening never replays pending or
uncertain requests. A repeated request ID cannot spend again. Cancel revokes local
adoption and stops owned CLI children; remote cancellation/charges may remain
unknown. Image requests and reported usage remain inspectable after later edits.
Layout and image repairs share a two-attempt automatic repair budget. Manual edits
and a smaller story remain available afterward. Export retry verifies existing
files and never regenerates an image. Restore creates a new revision and never
restores approval. Only explicit user approval authorizes final delivery.

See [conversation commands](docs/conversation.md), [saved contracts](docs/contracts.md),
[renderer selection](docs/rendering-decision.md), [provider capabilities](docs/provider-capabilities.md)
and [release acceptance](docs/acceptance.md).

## Verification

```sh
python3 -m unittest discover -s tests -v
```

Tests use synthetic material, disposable HOME/settings/workspaces and injected
providers. `INFOGRAPHIC_STUDIO_TEST_RENDERER=/absolute/installed/headless-shell`
enables real rendering checks; the tests never download or install it. The browser
journey is `tests/ui/journey.cjs` using a separately available Playwright test runtime.
Live provider generation/edit/inspection and owner illustration acceptance remain
separate release gates, never inferred from fixture success.

## Documents in, documents out

1. **New infographic → Add information.** Paste text, upload one or more files, or choose
   **Add a Google Doc or public page**. Review the captured text and any extraction gaps.
   Google Docs and Slides reads use the existing default gcloud account (like Blog Studio) and stable Drive version;
   all document tabs or slides are included unless you choose their IDs. Slide text, table text and speaker notes are captured; visual-only content is identified as an extraction gap. Import uses that exact preview, without
   refetching. PDF requires an explicitly installed `pdftotext`; scanned pages need a readable
   text copy. Word means `.docx`, without OCR, linked-resource reads or embedded-object analysis.
2. **Set the direction and page:** the audience, takeaway, must-show information and page
   size, then **Save brief**. The sheet has these two steps; its heading and its actions stay
   in view on a phone. Choose a story, build the page, edit, inspect actual pixels (the page
   pans with the keyboard once its region has focus), run checks and approve the exact revision.
   **Where this stands** is the one status surface: the route (Story, Draft page, Review
   and checks, Approved delivery) with the current step, what needs you (always naming the
   toolbar's one next action), your current work, the preview and the approved delivery,
   and what you can download. Every revision named is the page's revision: checks, a
   review and an approval are saved as revisions of their own, but they leave the page as
   it was, so the button, the files, the receipts, History, the team repository and the
   Document Library note on the page all name the revision you reviewed (the Document
   Library's own entry keeps the saved revision, as every studio records it). A restore is
   always new work with a number of its own. Reviewing or checking again after approval
   withdraws the approval until you approve again; the approved files stay in Saved files.
   **Review and finish** has three parts: your review of
   the actual page (**Review page**, required; recording it runs the local checks
   straight after), the checks (on this computer, starting no assistant or image request),
   and approval (your decision). Finished parts fold into one line, with **Review again**
   behind a disclosure. Assistant inspection is optional and separate.
   **Approve revision N** approves that exact checked revision and then prepares its final
   files locally in the same action, so the page never shows the approved revision as a
   new draft. If the files cannot be prepared (for example no renderer), the approval is
   kept, no approved file is offered, and **Prepare approved files** retries on this
   computer. **History** lists each page revision once, with what the revisions after it
   recorded; **Compare** says what changed in words (words by element, sources, story,
   layout) beside a thumbnail of each side, and keeps the saved fields under **Advanced**.
3. **Deliver approved page** offers a PDF, a Google Doc or both; the PNG, SVG and text
   downloads sit beside the page. PDF is the exact approved one-page
   local render. Google delivery creates a new native Doc containing the approved page image
   with alt text, plus editable accessible text and source notes. Artwork/layout in Docs is
   raster; the local SVG retains editable labels/charts. Inspect Google conversion in Docs
   before relying on its layout. The original source Doc is never overwritten or shared.
   A **Delivery receipt** lists every format you chose for that revision with what happened:
   the PDF as downloaded (with **Download PDF again**) and the Google Doc as delivered
   (**Open Google Doc**), not confirmed or not delivered. A partial result keeps what
   succeeded; retrying the PDF is local and sends nothing to Google, and **Check again
   without resending** only reads.

Google actions use the existing sign-in without an email prompt. Optional account/folder
overrides remain in advanced defaults. Delivery starts with Marketing Studio’s shared
Google/local choice. The account must already be signed in through an explicitly installed gcloud CLI with Drive/Docs
access. Settings/status never read credentials or initiate login. Tokens and resumable upload
session URLs remain in memory. A saved delivery intent precedes writes; after interruption,
**Reconcile Google delivery** performs reads only and never blindly creates another Doc.
PDF remains available when Google access fails. An old delivery remains historical after edits.

**Sources and facts → Add from Document Library** (also on **New infographic**) chooses
documents from the Document Library that every studio shares on this computer:
uploads, finished blogs, delivered decks and approved infographics. Each chosen
revision is checked, then captured as a source of this infographic only, so it keeps
working if the library changes. Like any new source, it clears the facts, story and
page built from earlier sources. The source says which library revision it came from,
and when a newer one is available, **Use revision N** takes it. Adding starts no
research, grants no web access and sends nothing to an assistant; it is refused while
the infographic is working. After **Approve revision N**, the
approved page's accessible text and PDF are kept in the library as an Infographic,
from the saved files. If that fails, the approval and files stand and **Keep in
Document Library again** retries it locally. See
[the Document Library](../../docs/shared-setup.md#the-document-library).

**Sources and facts → Use reviewed research** displays the exact infographic-purpose task
and explicit source mode. Give it to Harness Research separately, then select its complete
independently reviewed case. The installed helper verifies a bounded copied case; exact
manifest, review, helper revision, report/brief/evidence/facts and captures are retained.
The brief is supplied first; gaps, counterfacts and qualifications remain attached. No
public work runs in supplied-only mode. Missing or changed captures block claims/approval.

**Import selected studio material** lists readable material from a Blog Studio,
Presentation Studio or Training Studio `hub.json` folder. Select one file and review its
preview. Refresh/replacement is explicit and creates a new source revision.

**Team repository** uses the shared repository in shared settings. With none set, it says so
and offers **Configure shared repository**, which opens Shared settings at Your workspace;
**Share to team repository** offers the same, and with a repository set but not connected
it offers **Connect team repository**, so its main action never has to fail.
Saving or choosing Back returns to the same infographic and reopens Team repository; nothing
connects until you choose **Connect team repository**. A configured repository shows its
repository, branch, connection and last sync, read locally without fetching, so an offline
or signed-out connection still lists its last copy. Access, missing-repository and network
failures each name a recovery step without repeating Git's output or any credential, and
a failed first connection can be retried. It shows the last explicitly synced copy, its shared driver and omitted or
missing private inputs. Default sharing includes approved delivery files and a title only.
Editable project, source captures and artwork require separate selection and confirmation;
image briefs, prompts and job records are excluded. Set your shared display name and native
**Team Git email** before committing. Sync never force-pushes, resets or discards conflicts.
Failed pushes keep their commit; the library counts it and offers **Retry pending team push**. Takeover changes the driver;
importing its supported editable copy creates local work without approval. A local copy
already present is preserved. Unshared private inputs remain unavailable until supplied.
