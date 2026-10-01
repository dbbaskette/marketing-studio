# Blog Studio progressive disclosure roadmap

Blog Studio runs inside the user's Codex or Claude harness. The parent skill uses chat for choices, attachments, source links, voice setup, interviews, writing, and review. It loads the guidance needed for the current operation and keeps the selected outcome explicit. Local helpers preserve sources, profiles, article versions, and checkpoints.

Keep the existing browser prompt generator as an optional introduction for newcomers. It produces a starting request; it does not become a required application, a writing service, or a second place to maintain an article. A user can start directly in chat with a topic, manuscript, outline, source material, or a voice-profile request.

The current package implements the six routes, fourteen capability modules, and continuity helpers. The helper, refresh, and installer deterministic suite and package portability checks verify local behavior. Those results establish helper behavior and packaging; conversational quality and route selection still need a representative harness pilot.

## Repository updates are implemented

The installed bootstrap quietly fetches approved `main` for a new writing task, returns a compact status/path record, and progressively reads the pinned repository guidance. Existing articles resume their saved pin and runtime. Core executable updates are explicit managed installs with backup, repair, and rollback. See [installation](installation.md) and the [implementation record](superpowers/plans/2026-10-01-blog-studio-installation.md).

The bootstrap improves distribution and freshness. The craft/workspace instruction reductions below remain future work; a small installed entry does not by itself reduce the guidance read after it.

## Disclosure layers

| Layer | Reveal to the author | Load when needed | Persist between stages |
|---|---|---|---|
| 0 Discovery | Blog Studio can help with a blog or author voice | Skill name and description | Nothing required |
| 1 Starting outcome | Help with my draft; first draft; outline; from my outline; interview; discover an idea | Parent and entry flow; infer a clear request without showing the menu | Route and stop point |
| 2 Material | Attach, paste, supply links, reuse selected sources, or proceed without them | Intake and source module only when material is supplied | Original files, extracted text, roles, provenance, access limits |
| 3 Voice | Saved profile, learn my voice, described tone, or preserve this manuscript | Voice setup only for choosing/building/updating a voice; otherwise selected guide | Profile revision or tone choice |
| 4 Writing operation | The next useful question, outline, draft, or revision | One current craft module plus relevant references | Brief, interview notes, outline, original, current manuscript |
| 5 Focused review | Requested findings and proposed edits; optional deeper checks | Selected checks only: voice, factual support, shape, humanization, GEO | Findings and input fingerprints |
| 6 Finish or continue | Requested artifact, remaining gaps, optional next action | Export or repurposing only when requested | Checkpoint, version history, separate derived content |

These are loading boundaries, not mandatory screens. A supplied manuscript can go directly to editing. A clear first-draft request can outline internally and continue. Outline-only ends at the outline. Interviews ask one useful question at a time. Voice setup can run independently of an article.

## Current instruction token estimates

Measured October 1, 2026 from the local package. Each file estimate is its Unicode character count divided by four, rounded up. This is a planning approximation, not a model-specific tokenizer or provider usage report. All numbers exclude author material, generated prose, conversation history, host instructions, tool schemas, and tool results.

| Guidance loaded | Approximate new tokens | Condition |
|---|---:|---|
| Parent and entry flow | 2,085 | New task |
| Workspace instructions | 1,974 | Saving or resuming work; currently one large reference |
| Intake and source module | 781 | Incoming material |
| Voice setup and profile module | 941 | Building or changing a voice |
| Author interview | 275 | Interview route |
| Content strategy wrapper and original | 4,983 | Idea discovery or editorial strategy |
| Argument outline | 324 | Outline work; optional outline prompt adds 910 |
| Writer wrapper, original, composition, and outline | 6,820 | First draft; selected templates/research guidance add more |
| Copywriting wrapper, original, and headline lab | 2,572 | Titles, hooks, or CTA work |
| Editing wrapper, original, and revision | 4,451 | Editing or developmental feedback |
| Review coordination | 395 | Coordinating multiple requested checks |
| Voice check | 314 | Author rules and repetition |
| Factual support check | 340 | Claims against selected evidence |
| Humanization and its four-lens rubric | 1,179 | Requested prose improvement |
| GEO review | 344 | Requested retrieval/citation readiness assessment |
| Repurposing and export | 571 | Requested derivative or format; channel references add more |

The full Markdown, text, and prompt library is approximately **163,078 tokens across 80 files**. This includes every upstream template and supporting reference. It is an inventory ceiling, not a normal task load. The parent never needs to read the whole library to begin.

Read each unchanged reference once per task where possible. Disclosure avoids unnecessary reads; it does not remove already loaded text from an active conversation. Compaction or a new session can change what remains in context. Provider billing may include accumulated context repeatedly, with provider-specific caching. The unique-load figures below are therefore not total billed tokens.

## Representative routes

For the managed bootstrap, add approximately 697 tokens to each offline route below. The JSON inventory separates this add-on from the offline corpus. These estimates include the current parent, entry flow, and full workspace reference. They count each selected guidance file once. They assume the minimum listed guidance, not every conditional upstream reference.

| Route | Current guidance estimate | Additional author material planning allowance | Generated artifact planning allowance |
|---|---:|---|---|
| Outline with supplied sources | 5,164 | 2,000–6,000 for selected evidence; 300–800 for a saved voice | 500–1,200 for outline |
| First draft with supplied sources | 11,660 | 2,000–6,000 for evidence; 300–800 for voice; 300–800 for brief/outline | 1,500–2,200 for roughly 1,200–1,600 words |
| Quick edit of an existing draft | 8,824 | 1,500–2,200 for manuscript; 300–800 for selected voice/rules | 1,500–2,200 for revised draft, plus short notes |
| New voice setup | 5,781 | 4,000–10,000 for selected authored samples/background | 800–1,600 for guide and audition |
| Comprehensive review | 11,082 | 1,500–2,200 for draft; 2,000–6,000 for evidence; 300–800 for voice | 800–2,000 for findings; a rewrite is additional |

Author-material and output ranges are explicit planning assumptions, not measured user inputs. Full claim verification may require more evidence. A large upload stays in the source library; only relevant passages enter a particular writing operation. A summary helps orientation but does not replace the underlying passage when checking a claim.

## Instruction refinement roadmap

This roadmap extends the existing package. It does not authorize publication, installation into global skill folders, new paid services, or a hosted application. Development budgets estimate total input/output tokens across an agent's implementation, inspection, and verification work. They are separate from the runtime guidance figures above and should be revised after the first milestone.

| Milestone | Change and existing foundation | Dependency | Development budget | Acceptance |
|---|---|---|---:|---|
| M1 Smaller entry and explicit loading map | Keep the six implemented routes; reduce duplicated startup prose and document exactly which references are required versus conditional | Existing package | 8,000–15,000 | Parent plus entry approximately 800–1,200 tokens; direct draft/outline/voice requests skip unrelated menus; newcomer prompt still produces a valid request |
| M2 Smaller continuity reads | Split the existing workspace reference into discovery/resume, sources, profiles, articles, and reviews; return concise checkpoint summaries | M1 loading map | 12,000–20,000 | Routine operation loads approximately 200–500 tokens of helper guidance; pinned voice and original/history behavior preserved; all helper tests pass |
| M3 Concise craft guides | Distill the large upstream writing, editing, strategy, and title instructions into attributed working guides; retain immutable originals as optional deeper references | M1 | 20,000–35,000 | Routine writing guide approximately 1,000–1,600 tokens; edit guide 900–1,400; strategy guide 800–1,200; source support, voice, structure, and user stop points preserved |
| M4 Scoped reviews and evidence reads | Use existing fingerprints/statuses to reuse current checks; make targeted passage loading and requested review depth explicit | M2 and M3 | 10,000–18,000 | A quick polish loads only relevant checks; a changed draft stales affected findings; failed/unavailable checks never report clean results; evidence remains attributable |
| M5 Harness pilot and newcomer handoff | Exercise all six routes plus standalone voice setup inside the harness; keep the optional prompt generator aligned with the entry choices | M1–M4 | 12,000–22,000 | Direct chat and generated prompts reach the same workflow; attachments/URLs use real host tools; outline-only stops; interview asks one question; resume does not repeat setup; access failures are explicit |
| **Original refinement estimate** | **Five milestones** | | **62,000–110,000** | **Measured pilot results update the estimates** |

M2 and M3 can be sequenced independently after M1. No sub-agent execution or implementation is started by this roadmap.

## Runtime targets after the roadmap

Targets cover unique instruction loads for the normal route, with local continuity, and exclude author data and output. They are goals pending implementation and harness validation.

| Route | Current approximate guidance | Target guidance |
|---|---:|---:|
| Outline with sources | 5,164 | 2,000–3,000 |
| First draft with sources | 11,660 | 3,000–5,000 |
| Quick edit | 8,824 | 2,500–4,000 |
| Voice setup | 5,781 | 2,000–3,500 |
| Comprehensive review | 11,082 | 4,000–6,000 |

Reducing guidance must preserve useful behavior rather than merely shrinking files. The next useful slice is M1 followed by one outline-only pilot: start directly in chat, optionally attach sources, reuse a voice or choose a tone, save the outline, and stop. The optional prompt generator remains available throughout.

## Measurement record

The per-file inventory and route file sets are saved in `estimates/blog-studio-token-inventory.json`. Recompute after guidance changes. The roadmap itself, scripts, licenses, lock files, metadata, and browser preview are excluded from the instruction-library total. Shell execution of a helper does not load its full source into the model unless the agent chooses to read that source.

## Google Docs follow-up

The [Google Docs roadmap](google-docs-roadmap.md) recommends source intake and a review handoff/return loop first, with native comments, templates, and export following. Its modules load only for Google work. Connector availability and the team’s primary harness need validation before implementation.
