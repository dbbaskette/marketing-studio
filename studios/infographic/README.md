# Infographic Studio

Turn supplied information into one clear page. Paste notes, upload text/Markdown/PDF/Word/HTML files or selected CSV,
read a Google Doc or public HTTPS page, or import selected studio material; choose a story; build and inspect the
page; make focused edits; approve the exact revision and download PNG, one-page
PDF, editable SVG and accessible text. Explanatory artwork stays raster inside
SVG; labels and chart marks remain editable.

The first release implements comparison, process, timeline, number callouts,
parts-to-whole and conceptual explanations in A4, US Letter and 1080 × 1350 digital
portrait. Remote reads, reviewed research imports and selected team sharing are explicit actions.
The app does not start public research or OCR implicitly. Sources and generated files
stay in the local workspace; connecting a team library keeps an independent private clone.

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
repository. Team library → Connect or sync explicitly clones the configured repository;
only Share selected files commits and pushes a reviewed inventory.
The native Settings screen opens shared setup and separate image/renderer defaults.

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
Actual-page inspection uses the selected assistant's multimodal path, or you can
record your own review after viewing the current PNG at intended size. CLI help
and capability discovery are not proof of account access or successful generation.

## Editing and recovery

The desk exposes direct copy edits, a named-block or whole-story revision, a precise
saved image brief, reference-guided artwork edits, pixel inspection, findings,
comparison, history, restore and all four downloads. Earlier deliveries are labeled
when they no longer match current content. Required content, locked wording, located
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
2. Set the audience, takeaway and must-show information. Choose a story, build the page,
   edit, inspect actual pixels, run checks and approve the exact revision.
3. **Deliver Google Doc or PDF** offers either or both. PDF is the exact approved one-page
   local render. Google delivery creates a new native Doc containing the approved page image
   with alt text, plus editable accessible text and source notes. Artwork/layout in Docs is
   raster; the local SVG retains editable labels/charts. Inspect Google conversion in Docs
   before relying on its layout. The original source Doc is never overwritten or shared.

Google actions use the existing sign-in without an email prompt. Optional account/folder
overrides remain in advanced defaults. Delivery starts with Marketing Studio’s shared
Google/local choice. The account must already be signed in through an explicitly installed gcloud CLI with Drive/Docs
access. Settings/status never read credentials or initiate login. Tokens and resumable upload
session URLs remain in memory. A saved delivery intent precedes writes; after interruption,
**Reconcile Google delivery** performs reads only and never blindly creates another Doc.
PDF remains available when Google access fails. An old delivery remains historical after edits.

**Sources and facts → Use reviewed research** displays the exact infographic-purpose task
and explicit source mode. Give it to Harness Research separately, then select its complete
independently reviewed case. The installed helper verifies a bounded copied case; exact
manifest, review, helper revision, report/brief/evidence/facts and captures are retained.
The brief is supplied first; gaps, counterfacts and qualifications remain attached. No
public work runs in supplied-only mode. Missing or changed captures block claims/approval.

**Import selected studio material** lists readable material from a Blog Studio,
Presentation Studio or Training Studio `hub.json` folder. Select one file and review its
preview. Refresh/replacement is explicit and creates a new source revision.

**Team library** shows the last explicitly synced copy, its shared driver and omitted or
missing private inputs. Default sharing includes approved delivery files and a title only.
Editable project, source captures and artwork require separate selection and confirmation;
image briefs, prompts and job records are excluded. Set your shared display name and native
**Team Git email** before committing. Sync never force-pushes, resets or discards conflicts.
Failed pushes keep their commit for **Retry pending team push**. Takeover changes the driver;
importing its supported editable copy creates local work without approval. A local copy
already present is preserved. Unshared private inputs remain unavailable until supplied.
