# Shared document library and project context

Status: design approved; implementation pending.
Tracking issue: [Marketing Studio #205](https://github.com/dbbaskette/marketing-studio/issues/205)
contains the combined specification and implementation plan.
Date: 2026-10-29.

## Outcome and recommendation

Keep reusable uploads and completed studio work in one local document library.
Make that library available inside each studio. Remember browsing preferences per
studio, but save the actual context selection with each blog, presentation,
training or infographic. A new project starts with no documents selected.

This supports reusing a presentation in Blog Studio, or a blog in Presentation
Studio, without re-uploading it or carrying another project's context forward.
The library is shared storage; choosing documents is a project decision.

## Existing foundations

These findings describe checked-in code, not an audit of personal workspaces:

- Blog Studio's `blog_library.keep_written` retains finished blogs as `content.md`
  with revisions. Both guided Finish and writing-desk publish have integration
  paths. The desk reports a library-save failure without undoing publication.
- Blog Studio already has uploads, library search/filtering, multiple selection,
  roles, imports, and optional Team Hub sharing. These must remain compatible.
- `core/studio_core/shared_runner/documents.py` retains uploaded originals and
  readable `.txt` captures under each deck/training's `sources/supplied/`. Those
  documents are project-local and excluded from workspace sharing.
- Presentation Studio delivery records PowerPoint or Google Slides. Its current
  delivery contract does not guarantee a retained PDF library version.
- Infographic Studio has explicit selected-material handoffs from other studios,
  with hashes and ownership checks. It does not provide this general library.

## Storage and formats

The library has a readable folder outside the application repository. The default
is `library/` under the configured local Studios work location (normally
`~/Studios/library`). Save its resolved location on first explicit library setup
or use; a later change to workspace defaults must not move it. Standalone studios
use the same shared setting and library implementation without Marketing Studio
running. Existing project folders remain the studios' editable sources of truth.

| Content | Library versions to retain |
| --- | --- |
| Uploaded document | Original bytes plus readable `content.md` and conversion status |
| Completed blog | Exact saved Markdown, title, author and source-project revision |
| Completed presentation | PDF of the delivered local deck revision plus slide-ordered Markdown for context |
| Training material | Explicitly completed learner documents in Markdown; finished decks use PDF plus Markdown |
| Infographic | Approved local export and its readable text, through its native export boundary |

Markdown conversion means readable captured content with available headings,
page/slide locations and extraction gaps. It does not invent missing content or
promise a faithful reconstruction of every layout. Keep existing conversion
semantics and disclose limitations. An image-only PDF remains visible as needing
text; it cannot be selected as readable context until text is supplied. No OCR or
model summarization is started automatically.

Each document has a stable library ID and immutable revisions. A revision records
title, content type, origin, originating studio/project/revision when applicable,
author/date when known, original filename/media type, representations and hashes,
conversion method/status/gaps, and local/sharing scope. Type (Blog, Presentation,
Uploaded document, Training material, Infographic) is separate from origin
(Upload, Created here, Link, Google document, Imported). Unknown old entries stay
Uploaded document unless reliable existing metadata establishes another type.

Use readable per-document folders and a rebuildable local search index. Do not put
document bodies or the search index in shared settings. Keep stable identities
for Blog Studio records; an adapter maps native IDs/revisions into the library
without rewriting the Team Hub or losing voice/style metadata.

Save newly supplied files to the local library by default, with a visible
**Keep in library** choice; **Only this project** keeps them project-local.
Completed outputs are retained locally automatically. Repeated Finish/Deliver
operations reuse the document ID; changed content adds a revision. Failed library
retention is visible and retryable without repeating publication or delivery.

A completed presentation must not say **PDF saved** until a real PDF of the exact
delivered local deck exists and passes the existing rendering/export checks.
Delegate conversion to the existing Slides companion/runtime; do not add a second
slide-building pipeline or install tools. Missing conversion capability produces
**PDF needs export** with a local retry. Markdown may still be used if readable;
the incomplete PDF requirement remains visible. Retrying retention must not upload
another Google file or rerun a provider. Later edits in Google are not silently
treated as the local delivered revision.

## Context selector

Each studio's creation flow and editing desk has **Context** with **Add from
library**. The sheet uses the shared Golden Gate-inspired controls:

1. Search, **Type** (All types, Uploaded documents, Blogs, Presentations, Training
   material, Infographics), and **From** (All studios or a named studio).
2. Opaque rows showing checkbox, title, type, originating studio, updated date,
   available formats and readability. More filters hold author, status and origin.
3. A preview of readable Markdown with original/PDF download when available.
4. A selection bar with count, hidden selection count, Clear and **Use selected**.

Selections survive paging and filter changes. Select all is explicitly **on this
page**; any all-matching action is server bounded and applies the current filters.
Unreadable or unavailable revisions cannot be added and explain why. Use selected
validates every selected revision before changing project context. Cancel leaves
the project untouched. The initial default type is All types; remember filters
per studio. Never interpret a remembered filter as a selected document.

The project displays the documents actually in use, their revision and role, with
Preview and Remove. Use existing studio roles for facts/reference, messaging,
background or examples where supported; an example never becomes factual evidence
because it was selected. No voice/style learning starts from this picker.

Pin the selected revision and retain a project-owned snapshot of its readable
content and required original representations. Projects keep working if the
library changes or is unavailable. A new library revision shows **Update
available**; adopting it is explicit and uses the studio's existing input-change
and readiness rules. Context cannot change underneath an active assistant job.

Adding context alone does not start research, grant public-web access, change a
studio's research permissions, or send document text to an assistant. Subsequent
explicit work uses only selected documents and the existing role/permission rules.

Marketing Studio also offers a **Library** screen for browsing and intake, using
the same catalog. It does not select context for a project elsewhere.

## Compatibility, privacy and recovery

- Offer **Add existing work to library** with a preview of known configured
  workspaces, candidates, formats and gaps. Import only on that explicit action.
  Never crawl arbitrary home folders, start studios, move projects, or regenerate
  old PDFs in the background. Existing Blog Studio library entries remain usable.
- A local library copy does not grant team sharing. Preserve existing Blog Studio
  sharing behavior for its records; do not share newly retained cross-studio
  originals, PDFs or context snapshots without explicit sharing authority.
- Shared configuration uses `studios-config.json` and its adjacent lock with
  conflict checks and unrelated values preserved. Library writes use their own
  interprocess lock, atomic records, bounded reads and idempotent operation IDs.
- Preserve original bytes, validate paths and hashes, reject escaping links and
  incomplete records, and keep document text untrusted. Rebuild indexes from
  valid records. Concurrent writes must not lose a revision or attach wrong text.
- Removing context removes a selection, not the library document. Browsing or
  hiding an item must not delete source projects or old pinned revisions. Library
  deletion and remote synchronization are outside this initial implementation.

## Acceptance criteria

- A retained upload can be found by type and reused in a different studio without
  uploading again; its original and readable Markdown remain accessible.
- A finished blog retains Markdown; a delivered presentation retains an actual
  revision-matched PDF and Markdown, or clearly reports the export still needed.
- New projects start empty. Studio filter preferences persist independently;
  project document selections persist across restart and resume.
- Only selected revisions reach worker inputs. Roles, existing document limits,
  citation/provenance and public-web permissions survive the handoff.
- New revisions, missing files, unreadable captures, retries, concurrent writes
  and partial conversion failures have explicit recoverable states.
- Existing workspaces, Blog Studio library/Team Hub behavior and standalone
  launches keep working. No real user content or provider jobs enter tests.
- Selector works at phone width, with keyboard selection/focus, light/dark and
  reduced visual effects. Forms and reading surfaces remain opaque.

## Alternatives and scope

Separate libraries per studio would duplicate uploads and obstruct cross-studio
reuse. One automatic context set per studio would carry irrelevant documents into
new work. A central catalog with project selections gives reuse and predictable
inputs; immutable snapshots add storage but preserve reproducibility.

Initial scope excludes semantic/vector search, automatic summaries, OCR,
automatic document selection, persistent studio-wide context packs, remote-library
synchronization, changing team permissions, and deletion/retention policies.
