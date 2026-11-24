# Shared studio research workspace

Status: approved by the user on 2026-10-29; implementation in progress.

## Outcome and scope

Blog Studio, Presentation Studio, Training Studio and Infographic Studio use one
research source component and one Harness Research execution method. A person can
combine selected web links, Google Docs, uploaded documents and pasted text, then
explicitly allow or disallow searching beyond them. The studio supplies the
existing topic, audience, purpose and limits. Routine setup does not expose agent
management, JSON, filesystem handoff paths or Google account email fields.

This supersedes the Training Studio-only implementation direction in
`2026-10-29-parallel-research.md`. Retain useful transport/accounting tests and UI
work, but replace the unshipped Python packet/cache/merger with Harness Research
1.1 collection operations. No duplicate evidence registry or second research
service is introduced. Marketing Studio owns shared settings; Harness Research
owns evidence validation/assembly; studios retain content authoring and sync.

## Current implementation boundaries

- `core/studio_core/research_contract.py` supplies the existing schema-2 boundary.
- `core/studio_core/research_sites.py` already enforces document/site/public-web
  choices, including URL path restrictions and redirect checks.
- Presentation Studio and Training Studio use shared confined worker/document
  infrastructure under `core/studio_core/shared_runner/`.
- Blog Studio uses `synthesis_research.py` and `blog_worker` with source purposes
  and manuscript-specific Google baselines. Reference sources and manuscript
  editing targets are distinct.
- Infographic Studio already captures Google Docs/Slides/public URLs, but its
  research UI exposes a task JSON and reviewed-case directory rather than running
  the research. Replace that manual route in the primary flow.
- The four products share `ui-kit/style.css`; `drafting.js` demonstrates a portable
  JavaScript component with product adapters and no frontend build.
- The installed Harness Research is 1.1.0, while suite pins still identify 1.0.1.
  Adoption must explicitly pin the released source; existing runs retain their
  saved runtime/transport. No running job is migrated or restarted.

## Main interaction

Embed **Sources** in the parent's existing creation/edit workflow. Reuse the same
component on a dedicated **Research** view and when adding references later.

1. **Bring sources.** One multiline links field accepts multiple web links or
   Google Docs links together. Adjacent actions choose multiple files or paste
   text. A quiet **Use saved research** action selects owned workspace research
   by title/purpose/date/review status and exact digest. There is no arbitrary
   filesystem crawler or new global research library.
2. **See what will be used.** Show a compact source list with type, title, readiness,
   selected Google tab scope, Preview text, and Remove. Capture errors stay beside
   the affected row. Names/text are rendered as text, never executable markup.
3. **Choose expansion.** A visible checkbox says **Search for additional external
   sources**. With it off, read only supplied sources: a supplied public URL is
   permission to read that reference, not permission for unrestricted discovery.
   With it on, show the effective boundary in plain language. An additional
   **Limit additional searches to my approved sites** option uses the shared list;
   the list is not silently enabled just because it exists in shared settings.
4. **Start once.** A footer summarizes the actual source boundary and offers the
   parent's existing Continue/Start action, or Start research on the dedicated
   research view. Adding/capturing sources starts no provider job. Disable start
   when there is neither usable material nor permitted external search, with a
   direct inline explanation. No second source-approval ceremony follows a valid
   source choice.

A new panel starts with external search off. Existing saved choices and an
explicitly selected public-research preset retain their visible choice. Changing
sources never silently toggles search permission. The same request can use local
material plus selected public URLs with external search off.

File capabilities come from the common server intake layer. Initially consolidate
PDF, DOCX, TXT, Markdown and HTML support, preserving existing extraction limits
and reporting missing PDF extraction support. Keep specialist primary deck/PPTX,
CSV/data and artwork ingestion in their existing workflows. Preserve existing
Google Slides reference support where available; identify link type automatically.
Do not advertise OCR, image understanding, arbitrary Drive browsing or spreadsheet
extraction through a generic upload field.

## Google Docs behavior

- Detect Google links automatically; reuse shared Marketing Studio defaults and
  the existing locally selected Google sign-in. No required email field, repeated
  credential form, service-account setup or new provider is introduced.
- A tab-specific URL preselects that exact tab. A full-document URL shows **All N
  tabs included** with an inline **Choose tabs** disclosure. List human-readable
  tab names and allow multiple selections for reference documents. Invalid/missing
  selected tabs cause a local actionable refusal, never fallback to all tabs.
- Scope stored captures, originals and provider inputs to selected content;
  distinguish listing tab metadata from reading source content. Verify the actual
  Google API scoping support during implementation before making stronger
  network-access claims. Unselected tab content must not be retained or passed to
  research. Preserve document identity, selected IDs and revision/capture receipts.
- Reuse the proven Blog Studio native tab extraction/scoped snapshot behavior;
  do not use whole-document Markdown/DOCX export as a single-tab fallback.
- Reference import is read-only. Blog Studio's primary manuscript import,
  proofreading, local edits, suggestions/comments and writeback keep their own
  baselines and explicit author-facing actions. Adding a research reference never
  creates Google write permission or changes the original.
- Preview text includes extraction limitations without requiring an extra checkbox
  on every ordinary readable source. Material gaps require a clear decision to
  retry, remove the source, or proceed explicitly without that source. Do not
  silently treat unreadable/omitted content as fully read.

## Quiet advanced controls

**Research options** is collapsed by default. It contains an optional focus/exclude
note, approved-site details and a worker choice: Automatic (up to 3), 1, 2 or 3.
Automatic is bounded by the current host capacity, effective studio limits and
remaining supported per-run allowance. One worker means sequential collection;
independent final review still uses a separate invocation. Worker settings cannot
raise budgets, install providers or bypass host restrictions. Keep per-request
worker choices local; changing a shared default uses the existing shared settings
lock/staleness rules. Do not claim an account-wide or cross-studio dollar ceiling
where the existing system cannot enforce one.

## One shared execution contract

Add a shared core research session/controller and a thin host transport interface.
The transport owns actual isolated invocations, confined source tools, effective
model selection, reservations, cancellation and terminal observations. Product
adapters supply those capabilities and existing state/ownership callbacks. They
must not each implement their own collection loop, packet validator or merger.

The controller uses the released Harness Research 1.1 interfaces:

- `asset init|intake|source|status` for a caller-specified private local topic asset;
- `collection init|register|capture|accept|finish|assemble|retry|pause|resume|stop|invalidate|status`;
- existing `synthesis save|template|review|verify` for the exact final digest.

Only host-owned code registers actual invocation identities, capture receipts and
terminal observations. Worker-returned JSON cannot register its own permissions,
identity or reviewer. The coordinator partitions the approved brief/questions into
a few independent themes, with no extra planning model call or fixed quota.
Investigators get only the assignment, relevant stage guidance, scope and source
access. Synthesis consumes the immutable helper registry. The final checker is a
separate invocation from every factual author, including zero-fact investigators.
All output remains schema 2 and uses returned manifest paths, supporting both new
root-level topic assets and existing `research/` case layouts.

New starts pin `harness-collection-v1` separately from companion capability.
Existing serial records stay readable and resume serially with their saved helper.
Do not adopt the unshipped Training Studio schema-5 prototype as an installed-run
migration contract. Audit real record readers before choosing each product's
additive execution record/version bump.

Use one private draft/source staging model with host-issued source IDs, immutable
snapshot identities, read status and revision tokens. Multi-tab selection is part
of source identity. Backend start validates the exact source/request revision;
idempotency prevents duplicate starts from double taps/reconnects. A stale input,
owner change or stop cannot adopt a late result. Shared endpoints/facades must use
the product's existing session/authentication and confined workspace boundaries.
Do not expose a new unauthenticated central process or arbitrary local paths.

Keep the current DNS/redirect/SSRF controls and the stricter path-aware approved-site
policy in the host fetcher. Harness Research's hostname restriction is additional
validation, not a replacement for those guards. Source instructions remain data;
public search queries do not disclose private supplied material.

## Progress, correction and reuse

Use the same progress component everywhere: **Collect evidence → Combine findings
→ Independent check → Ready**. Show useful area titles and Working / Evidence kept
/ Needs retry; do not show a fake percent or ungrounded finish estimate. Optional
details contain worker status, source warnings, total assistant time and supported
cost information. Main timing distinguishes elapsed and active wall time. Active
time uses interval union; assistant time uses sum. Confirmed terminal observations
are required to settle stopped intervals; unknown timing/cost remains unknown.

Pause prevents new dispatch and lets current work checkpoint. Stop requests actual
host cancellation and invokes helper stop; show cancellation pending until terminal
observation. Retry failed/refused areas, preserving valid unaffected packets.
Use a prose-only correction when the evidence is sound. Every changed final dossier
receives fresh independent review, within the existing correction bound.

A complete result offers Open report, Open brief, optional evidence/details and
Use research to continue the parent workflow with the exact reviewed digest.
Draft/refused/stale results never appear Ready. Sync failure is shown separately;
retry sharing without rerunning completed research. Existing sources/captures stay
available after failure/restart. Reuse an owned asset only after integrity/purpose/
permission compatibility is checked; metadata matching alone is insufficient.

## Fit in each product

| Product | Use the shared panel for | Preserve |
| --- | --- | --- |
| Blog Studio | New-blog research, references, optional evidence/fact-check research | Polish/proofread without research; source roles, voice/inspiration exclusions; primary Google Doc editing and suggestions |
| Presentation Studio | Topic/document/deck source selection and optional supporting research | Existing deck edits, native delivery, brand/slide review gates |
| Training Studio | Research for all requested levels/materials and later reference updates | Teaching blueprint/material selection, current training progress and ready decisions |
| Infographic Studio | Optional research from sources/topic, direct reviewed-result consumption | Supplied-information story planning without research; visual composition, data input, image jobs and final approval |

Turning off external search does not turn off analysis of supplied material.
Turning on research is distinct from enabling external search. Preserve each
parent workflow's intentional research/no-research choice; the common source UI
must not force a research stage into every content operation.

## Visual and accessibility contract

Use `ui-kit/style.css` with one `ui-kit/research.js` source/progress component.
Product adapters supply copy/context/primary action and existing authenticated API
transport. The shared component owns source list, tab picker, scope summary,
advanced options, progress and recovery behavior. Distribute the same bytes into
standalone installs using the existing approved shared-link/package mechanism.
No framework, new library, font download, or frontend build step.

Use opaque forms/reading surfaces; reserve material for existing chrome/sheets.
Retain each studio's accent through `data-product`. Preserve draft fields, focused
control and open disclosures during polling. Use labelled native controls, visible
status/errors, safe text nodes and at least 44px touch targets. Verify phone width,
long titles, light/dark, keyboard use and reduced effects.

Preview: `docs/design/shared-research-preview.html`. It uses synthetic in-memory
sources and sample progress; it neither reads links/files nor starts providers.
Preview-only studio/state/phone controls are not product controls.

## Acceptance

- A mixed set of files, URLs, pasted text and selected Google tabs follows the same
  capture/start/progress/retry/review path in all four independently runnable studios.
- No Google account email is required when a usable shared/default account exists.
- External search permission is visible, saved and enforced at every public fetch;
  existing approved-site path restrictions survive the new helper integration.
- Worker capacity and supported per-run allowance are shared across jobs in the
  session rather than duplicated. Unknown provider costs stay explicit.
- Successful packets survive one peer failure, process restart and focused retry;
  late/stale/unregistered results cannot become reviewed evidence.
- Saved research can be reused by exact digest; local completion and team sharing
  have separate status/retry. Old serial jobs resume unchanged.
- Blog polishing, existing-deck edits and supplied-only infographic creation remain
  accessible without research. No real studio state/provider jobs are used in tests.

## Alternatives and limits

Copying similar source forms would retain four behavior forks and is rejected.
Putting orchestration inside the UI or reimplementing collection in Python is
rejected: use the helper's portable contract with host-owned execution. A separate
research web service adds installation/session overhead and is unnecessary.

This scope does not add a global research library, autonomous refresh, new global
quota service, Google writeback, OCR, automatic image generation or new downstream
content formats. Live Google/provider acceptance is separate from synthetic
verification and requires an explicit representative test request.
