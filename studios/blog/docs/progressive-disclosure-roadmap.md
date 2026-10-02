# Blog Studio progressive disclosure roadmap

Blog Studio runs inside the user's Codex or Claude harness. The parent skill uses chat for choices, attachments, source links, voice setup, interviews, writing, and review. It loads the guidance needed for the current operation and keeps the selected outcome explicit. Local helpers preserve sources, profiles, article versions, and checkpoints.

Keep the existing browser prompt generator as an optional introduction for newcomers. It produces a starting request; it does not become a required application, a writing service, or a second place to maintain an article. A user can start directly in chat with a topic, manuscript, outline, source material, or a voice-profile request.

The current package implements the six routes, twenty capability modules, and continuity helpers. The helper, refresh, and installer deterministic suite and package portability checks verify local behavior. Those results establish helper behavior and packaging; conversational quality and route selection still need a representative harness pilot.

## Repository updates are implemented

The installed bootstrap quietly fetches approved `main` for a new writing task, returns a compact status/path record, and progressively reads the pinned repository guidance. Existing articles resume their saved pin and runtime. Core executable updates are explicit managed installs with backup, repair, and rollback. See [installation](installation.md) and the [implementation record](superpowers/plans/2026-10-01-blog-studio-installation.md).

M1 reduced the parent plus entry to **1,195 tokens** (787 + 408), down from 2,329. Required capability reads and conditional support reads are explicit. The installed bootstrap is measured separately at **857 tokens**. See the [M1 validation record](m1-entry-validation.md). M2 and M3 are now implemented: focused continuity references and four attributed working craft guides. See the [combined validation record](m2-m3-validation.md). M4 scoped reviews are implemented; I4/M5 pilot progress and remaining live checks are recorded in [the validation record](i4-m4-m5-validation.md).

The current parent plus entry is **1,342 estimated tokens**; the bootstrap is **1,054**. Readiness adds **477** only when needed; workspace plus context controls add **767**. Google modules remain optional. Runtime 1.3.0 adds these usability controls; see [live validation](usability-validation.md).

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

## Earlier instruction token estimates (historical)

The following baseline predates the house-style addition. For the current package, use the dated table below and the machine-checked inventory. Each file estimate is its Unicode character count divided by four, rounded up. This is a planning approximation, not a model-specific tokenizer or provider usage report. All numbers exclude author material, generated prose, conversation history, host instructions, tool schemas, and tool results.

| Guidance loaded | Approximate new tokens | Condition |
|---|---:|---|
| Parent and entry flow | 1,240 | New task |
| Workspace router + one routine operation | 450–498 | Create/save, resume, sources, profiles, or reviews; read only the needed operation |
| Workspace router + mechanical checks | 364 | Requested lint/preservation/count operation |
| Intake and source module | 902 | Incoming material; source storage is additional |
| Voice setup and profile module | 1,004 | Building or changing a voice; profile storage is additional |
| Author interview | 335 | Interview route |
| Strategy working guide | 1,199 | Idea discovery/editorial strategy; original is optional |
| Argument outline | 383 | Outline work; optional outline prompt adds 910 |
| Writing working guide | 1,576 | Drafting; specialized templates/research support are conditional |
| Title/copy working guide | 847 | Titles, hooks, or requested CTA; optional headline lab adds 144 |
| Editing working guide | 1,399 | Polish/feedback; controlled revision support is conditional |
| Review coordination | 591 | Multiple requested checks |
| Voice check | 373 | Selected author rules and repetition |
| Factual support check | 966 | Claims against selected passages, including evidence-selection guidance |
| Humanization | 435 | Requested prose feedback; deep four-lens rubric adds 855 |
| GEO review | 399 | Requested retrieval/citation readiness assessment |
| Repurposing and export | 687 | Requested derivative/format; channel references add more |

The full Markdown, text, and prompt library is approximately **171,712 tokens across 95 files**. This includes every upstream template and supporting reference plus the authored working guides; retained archives explain the slight inventory growth. It is an inventory ceiling, not a normal task load. The parent never needs to read the whole library to begin.

Read each unchanged reference once per task where possible. Disclosure avoids unnecessary reads; it does not remove already loaded text from an active conversation. Compaction or a new session can change what remains in context. Provider billing may include accumulated context repeatedly, with provider-specific caching. The unique-load figures below are therefore not total billed tokens.

## Representative routes

For the managed bootstrap, add approximately 857 tokens to each offline route below. The JSON inventory separates this add-on from the offline corpus. These estimates include the parent, entry flow, workspace router, and every focused operation required by the recorded scenario. New-article routes include creation and saving; supplied material includes source storage. Editing/review scenarios use a saved article; importing a new manuscript adds intake/creation work. They count each selected guidance file once. They assume the minimum listed guidance, not every conditional upstream reference.

| Route | Current guidance estimate | Additional author material planning allowance | Generated artifact planning allowance |
|---|---:|---|---|
| Outline with supplied sources | 3,568 | 2,000–6,000 for selected evidence; 300–800 for a saved voice | 500–1,200 for outline |
| First draft with supplied sources | 5,144 | 2,000–6,000 for evidence; 300–800 for voice; 300–800 for brief/outline | 1,500–2,200 for roughly 1,200–1,600 words |
| Edit plus saved voice-rule review | 4,555 | 1,500–2,200 for manuscript; 300–800 for selected voice/rules | 1,500–2,200 for revised draft, plus short notes |
| New voice setup | 3,928 | 4,000–10,000 for selected authored samples/background | 800–1,600 for guide and audition |
| Light polish without a separate review | 3,399 | 1,500–2,200 for manuscript; selected voice | Revised passages or draft |
| Comprehensive review | 5,201 | 1,500–2,200 for draft; 2,000–6,000 for evidence; 300–800 for voice | 800–2,000 for findings; a rewrite is additional |

Author-material and output ranges are explicit planning assumptions, not measured user inputs. Full claim verification may require more evidence. A large upload stays in the source library; only relevant passages enter a particular writing operation. A summary helps orientation but does not replace the underlying passage when checking a claim.

## Instruction refinement roadmap

This roadmap extends the existing package. It does not authorize publication, installation into global skill folders, new paid services, or a hosted application. Development budgets estimate total input/output tokens across an agent's implementation, inspection, and verification work. They are separate from the runtime guidance figures above and should be revised after the first milestone.

| Milestone | Change and existing foundation | Dependency | Development budget | Acceptance |
|---|---|---|---:|---|
| M1 Smaller entry and explicit loading map — implemented | Six routes retained; concise entry and explicit required/conditional reads | Existing package | 8,000–15,000 original estimate | Parent + entry 1,195 tokens; current-session outline-only smoke and generated request checks recorded; full live discovery/route validation remains M5 |
| M2 Smaller continuity reads — implemented | Workspace router plus focused operations; compact author-facing checkpoints | M1 | 12,000–20,000 original estimate | Routine operation 450–498 tokens including router; originals/history, pins, statuses verified; advanced operations load only when needed |
| M3 Concise craft guides — implemented | Four attributed working guides; immutable originals optional | M1 | 20,000–35,000 original estimate | Writing 1,576; editing 1,399; strategy 1,199; titles 847 tokens. Synthetic comparisons preserve evidence, voice, structure, and stop points |
| M4 Scoped reviews and evidence reads — implemented | Use existing fingerprints/statuses to reuse current checks; make targeted passage loading and requested review depth explicit | M2 and M3 | 10,000–18,000 | A quick polish loads only relevant checks; a changed draft stales affected findings; failed/unavailable checks never report clean results; evidence remains attributable |
| M5 Harness pilot and newcomer handoff | Exercise all six routes plus standalone voice setup inside the harness; keep the optional prompt generator aligned with the entry choices | M1–M4 | 12,000–22,000 | Direct chat and generated prompts reach the same workflow; attachments/URLs use real host tools; outline-only stops; interview asks one question; resume does not repeat setup; access failures are explicit |
| **Original refinement estimate** | **Five milestones** | | **62,000–110,000** | **Measured pilot results update the estimates** |

M1–M4 are implemented. I4/M5 have reproducible Tart/newcomer checks. Per user direction, signed-in Mac and live Codex/Claude tests remain in issues #8/#9 and run last, after implementation work; original development ranges are historical planning estimates, not measured consumption. Roadmap estimates are not execution budgets or permission for additional services.

## Runtime targets after the roadmap

Targets cover unique offline instruction loads for the normal route, with local continuity, and exclude author data and output. Add the separately measured bootstrap for a managed installation. They are goals pending implementation and harness validation.

| Route | Current approximate guidance | Target guidance |
|---|---:|---:|
| Outline with sources | 3,568 | 2,000–3,000 |
| First draft with sources | 5,144 | 3,000–5,000 |
| Quick edit | 4,555 | 2,500–4,000 |
| Voice setup | 3,928 | 2,000–3,500 |
| Comprehensive review | 5,201 | 4,000–6,000 |

Reducing guidance must preserve useful behavior rather than merely shrinking files. The M1 outline-only smoke reused supplied notes and tone, saved and reopened the outline, and stopped before a draft. M2–M4 reduce continuity/craft/review reads. Comprehensive feedback is now 5,201 tokens; a light polish without separate checks is 3,399. The explicitly broader edit-plus-review scenario remains 4,555. Some routes still exceed final targets; M5 must validate behavior and revise targets from observed unique reads. The optional prompt generator remains available throughout.

## Measurement record

The per-file inventory and route file sets are saved in `estimates/blog-studio-token-inventory.json`. Recompute after guidance changes with `python3 scripts/measure_guidance.py`; `--check` verifies the recorded inventory. Route file sets remain explicit planning scenarios, not traces of every possible conversation. The roadmap itself, scripts, licenses, lock files, metadata, and browser preview are excluded from the instruction-library total. Shell execution of a helper does not load its full source into the model unless the agent chooses to read that source.

## Google Docs workflows

G0–G3 are implemented as six conditional modules plus runtime 1.2.0 transfer checkpoints. The [Google Docs roadmap](google-docs-roadmap.md) separates measured instruction costs from provider/plugin overhead. Source intake, handoff/return, comments, templates and export/sharing remain inside the harness; actual connector capabilities are discovered per session. Authenticated Google verification is deferred to G4 (#15).

## Implemented Team Hub disclosure

The parent adds a conditional hub route. The following are measured character-based estimates for the current authored instructions; add them only when the operation needs them, alongside the ordinary writing route. They exclude actual shared records and artifacts.

| Team operation | Router plus focused reference |
| --- | ---: |
| Setup | 1,350 |
| Memory | 1,417 |
| Sync | 1,341 |

H1–H3 and the H4 installer/docs slice are implemented; the 58–95k development range in the approved Team Hub plan remains a planning estimate, not measured consumption. Deterministic local member tests are distinct from the pending real GitHub/harness pilot.

The data-boundary reference adds approximately **1,002 tokens** only when external operations or upstream service suggestions are relevant. The essential privacy constraint is in every parent/module.

## House-style disclosure — October 2, 2026

The [house guide](house-style-guide.md) is implemented as conditional references,
not a new globally loaded skill. Ordinary software-blog writing reads the core
once and only applicable leaves. Setup, source intake and voice learning skip it.
Team preferences use existing scoped rules and selected article revisions.

| Selected style guidance | Additional unique estimated tokens |
| --- | ---: |
| Core house guide | 623 |
| Core + article forms | 1,643 |
| Core + software claims | 1,177 |
| Core + software claims + practical examples | 1,661 |
| Core + software claims + performance evidence | 1,675 |
| Visual extension alone | 347 |
| Source map (maintenance only) | 933 |

These are additions to the relevant writing route. If planning and drafting both
need the core, count it once; combine route file sets, not their totals. A visual
adds only its own leaf. The source map is not required to write an article.

Current ordinary route estimates, before conditional house references:

| Route | Estimated tokens |
| --- | ---: |
| Outline with sources | 3,999 |
| First draft with sources | 5,615 |
| Edit + voice-rule review | 5,119 |
| Voice setup | 4,117 |
| Light polish | 3,903 |
| Comprehensive review | 5,753 |

Add 1,054 for the managed bootstrap. All values
exclude author data, generated output and provider/tool overhead; character-based
estimates are not billed token counts. Existing article guidance remains pinned.
House-style guidance alone needs no runtime change. The accompanying Google
formatting helpers require the 1.5 installer update.
