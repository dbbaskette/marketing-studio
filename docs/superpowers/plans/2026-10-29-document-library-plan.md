# Shared document library implementation plan

Status: design and implementation plan approved; implementation pending.
Tracking issue: [Marketing Studio #205](https://github.com/dbbaskette/marketing-studio/issues/205)
contains this plan and the [design](../specs/2026-10-29-document-library-design.md).
Date: 2026-10-29. Implementation and integrated verification owner: assign when implementation begins.
No application behavior has changed yet.

## 1. Shared library records and configuration

Add a `core/studio_core/document_library/` package for versioned records,
representations, local catalog/search, bounded intake, atomic/idempotent writes,
locking and pinned snapshot export. Reuse existing safe document conversion
helpers through a small shared interface; product imports such as `home` and
`runner` must not become dependencies of the generic store.

Extend `core/studio_core/studios_config.py`, shared preferences/setup and relevant
native bindings for a frozen library location and per-studio browsing filters.
Follow the existing adjacent settings lock and outdated-form conflict protocol.
Creating/opening the library must not initialize an unconfigured studio workspace.

Acceptance: originals plus Markdown, stable IDs, immutable hashed revisions,
idempotent retries, rebuilt index and standalone access. Development checks use
temporary roots and cover conflicting writes, interrupted writes, unsafe paths,
oversized input, unreadable files and settings preservation.

## 2. Existing data adapters and explicit adoption

Adapt Blog Studio's `blog_library.py`, `library_add.py`, `management.py`, source
records and existing revision readers. Preserve native roles, collection/author
metadata, voice/style learning, Team Hub identities and existing sharing policy.
Expose legacy entries through a catalog adapter; materialize a shared immutable
snapshot only when explicitly used or adopted. Record its native ID/revision map.

Use the remembered-workspace contracts in `marketing_studio/workspaces.py` through
a shared reader usable by standalone studios. Add a preview/confirm adoption path
for known uploads and completed work. Keep existing folders in place and report
unavailable formats. Do not start renderers, assistants or remote reads on browse.

Acceptance: pre-existing Blog Studio entries stay usable; adoption is bounded,
retryable, records what was imported and never moves/overwrites source work.
Checks include synthetic old/new records, duplicate IDs across workspaces,
unknown type metadata, missing roots, linked paths and repeat adoption.

Depends on step 1.

## 3. Retain newly supplied and completed content

Integrate local retention with Blog Studio upload and Finish/publish hooks in
`studios/blog/skills/blog-studio/scripts/`. Integrate deck/training document intake
through `core/studio_core/shared_runner/documents.py` and the native wrappers.
Add the visible Keep in library choice without changing old sharing authority.

Extend Presentation Studio's `runner/steps/deliver.py` and native Training Studio
completion/delivery hooks. Add a PDF export adapter beside existing
`core/studio_core/shared_runner/slides.py` companion integration, using the
capabilities actually supported by the locked runtime. Keep native editable
PowerPoint/Google delivery intact. Derive readable slide Markdown from the exact
delivered composition; retain ordering, notes where available and provenance.
Record delivery success separately from PDF/Markdown/library-save success.

Integrate Infographic Studio through `runner/documents.py`, native approved
exports and `runner/handoffs.py`; preserve ownership, source permission and exact
approval checks. Training document/deck completion uses the same record contract.

Acceptance: repeated completion saves one document with new revisions only for
changes; real PDF bytes match the delivered local deck; retrying local retention
does not repeat Google delivery or provider work. Missing render capability and
conversion failure remain visible and recoverable. Development checks use fake
companions plus a disposable synthetic deck against the installed locked renderer
where available; record any actual PDF-rendering coverage gap explicitly.

Depends on steps 1–2.

## 4. Project context and worker handoff

Add project context manifests binding library ID, revision, role and hashes to
project-owned snapshots. Reuse Blog Studio source pinning, the shared deck/training
document source contract, and Infographic Studio's located-input handoff.
Write a state-transition matrix in this plan during implementation for add,
remove, explicit update, busy refusal, unavailable source and unchanged retry.
Keep existing input/readiness invalidation rules in each native studio.

Acceptance: a resumed project reads its pinned content despite later library
edits or loss of the library folder. New projects never inherit selected content.
Selection updates are atomic, revision checked and refused while dependent work
is active. Only selected readable sources reach workers; examples remain examples
and research permissions remain unchanged. Development checks own this matrix,
context size limits and worker-input assertions with synthetic sources.

Depends on steps 1–3.

## 5. Library screen and shared context selector

Add shared JavaScript/CSS under `ui-kit/` using existing filter, selection-bar,
sheet, input and opaque reading controls. Integrate with Marketing Studio home
and the four native pages, including Blog Studio's existing picker rather than
creating a competing path. Inspect native routes under the existing authenticated
page implementations before adding bounded list/preview/select endpoints.

Implement search/type/studio filters, more filters, representation preview,
checkboxes, retained selections across paging/filtering, explicit page/all-matching
selection boundaries, and the project Context list. Persist browse filters per
studio and context selections per project. Render no private local paths or
document HTML as trusted markup.

Acceptance: cancel changes nothing; Use selected validates all revisions; hidden
selection counts are accurate; unreadable states explain recovery. Browser
journeys cover cross-studio reuse, keyboard focus and dismissal, narrow layout,
long titles, empty/loading/error states, dark/light and reduced effects.

Depends on steps 1–4.

## 6. Integrated verification and documentation

Update README, architecture/shared-setup documentation and affected native user
guides to explain the library location, Markdown/PDF retention, browsing versus
context selection, local scope, export failures and explicit adoption. Add a
synthetic standalone-launch journey showing cross-studio context reuse.

Run focused checks at the preceding functional milestones. Before the single
full relevant run, read the installed shared Local CI reference,
`docs/testing.md` and the applicable native CI instructions. Use the shared Tart
runner through `scripts/ci/tart-macos.sh` (inspect `--dry-run` first) and the
existing full `scripts/ci/check.sh` guest path. Do not alter release workflows.

Because storage and Blog Studio synchronization boundaries change, run the
required native CLI/Hub walkthrough against a disposable local synthetic Hub:
create/join, intake, blog save/review, cross-clone resume/edit, offline queue/retry,
status, readable folders and overwrite protection. Reuse valid unchanged evidence.
No live remote repository, credentials, personal settings or paid provider jobs.

Retain logs identifying the tested tree/commit and environment. Separate real
renderer evidence from stand-ins and remote/provider acceptance. Report required
remote gates separately if they cannot start. Approval covers implementation and
local verification, with publication/deployment outside this plan.

## Review focus

- Blog Studio local/library/Team Hub identities and permissions stay compatible.
- Shared browsing never silently selects or discloses documents to a worker.
- PDF retention binds the delivered revision and cannot repeat external delivery.
- Project snapshots, library records and settings have distinct concurrency rules.
- Standalone and partially configured installations do not require the umbrella
  process, initialize other studios, or install new tools.
