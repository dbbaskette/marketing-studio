# M2–M3 focused guidance — October 1, 2026

Implemented locally for [M2 #5](https://github.com/dbbaskette/blog-studio/issues/5) and [M3 #6](https://github.com/dbbaskette/blog-studio/issues/6), based on `49688ba`.

The workspace reference is now a small router with focused resume, source, profile, article, and review instructions. Article creation, exceptional guidance restoration, and mechanical checks have their own conditional references. Existing callers link to the relevant operation. Four craft modules now contain attributed working guides; their immutable originals and supporting references remain available for optional depth.

The runtime helpers and installed bootstrap are unchanged. This is repository guidance that compatible runtime 1.1.0 can load after publication without reinstalling. The offline skill archive is rebuilt. M2's concise checkpoint is an author-facing summary of existing metadata; the helper JSON interface remains unchanged. Source bodies and unrelated saved artifacts are not loaded just to report status.

## Measured loads

Estimates are per-file Unicode characters divided by four, rounded up. They exclude source/manuscript content, conversation history, tool output, host instructions, and provider billing. The shared workspace router is 182 tokens and is counted once in each operation below; a task spanning multiple operations reads their union, not one operation's number for the entire task.

| Continuity operation, including router | Tokens |
| --- | ---: |
| Discover/resume, including pinned voice lookup | 492 |
| Sources | 487 |
| Profiles | 498 |
| Article save/checkpoint | 491 |
| Article creation | 450 |
| Reviews/derived content | 466 |
| Exceptional guidance restoration | 473 |
| Mechanical checks | 364 |

The previous workspace reference loaded 2,197 tokens for any operation. New-article tasks also need the article-save guide; shared work and exceptional restoration add their selected hub/pin guidance. These extra reads are not hidden in the per-operation target.

| Routine craft read | Before: wrapper + required original | Current working guide | M3 target |
| --- | ---: | ---: | ---: |
| Writing | 6,237 | 1,576 | 1,000–1,600 |
| Editing | 4,225 | 1,399 | 900–1,400 |
| Strategy | 5,039 | 1,199 | 800–1,200 |
| Titles/copy | 2,483 | 847 | Measure; no fixed target |

Conditional outline, composition, revision, headline, and deep-research references are additional when applicable. Full route estimates include the explicit files recorded in the token inventory:

| Offline route | M1 baseline | M2–M3 |
| --- | ---: | ---: |
| Outline with supplied sources | 4,669 | 3,544 |
| First draft with supplied sources | 11,220 | 5,120 |
| Quick edit of a saved article | 8,267 | 4,519 |
| Standalone voice setup | 5,285 | 3,904 |
| Comprehensive review of a saved article | 10,690 | 6,639 |

Add the unchanged 857-token bootstrap for managed installations. The parent plus entry stays at 1,195 tokens. New source/manuscript intake, voice changes, optional templates, and hub operations add their applicable guidance. Several final roadmap route targets still need M4/M5 refinement and validation.

The full offline library is 170,621 tokens across 93 files. It grows because optional originals remain alongside the authored guides; routine reads shrink. `scripts/measure_guidance.py --check` verifies the inventory, routes, continuity operations, and craft estimates from the actual files.

## Behavioral checks

[Five inspectable baseline/current comparisons](evaluations/m2-m3-craft-samples.md) cover outline, short draft, controlled edit, topic choices, and titles. They use synthetic notes and a specified voice. Both sets were generated during this session with baseline/current guidance in shared context; this is a manual regression comparison, not isolated model evaluation or proof of general quality.

The outputs keep source scope and the supplied quote, remove an unsupported 30% claim, retain distinct section/topic jobs, stop at the requested artifact, and avoid invented metrics or promotional additions. Source/private-input restrictions precede the optional archive links in every revised craft module. No additional model, research, media, or publishing service was called.

The current Codex session then exercised the focused instructions through existing helpers in `/tmp/blog-studio-m23-smoke-tgl4vah3/`. It initialized a disposable workspace, stored the source and a voice guide, created an outline-only article, saved a separate requested draft, and revised an imported manuscript. Readback verified:

- The outline-only article had its outline and no draft.
- Imported original bytes and the earlier edited version remained available.
- A profile update left the article on voice revision 1.
- A later draft edit made the completed proofread stale.
- A source update retained the article's revision-1 baseline and exposed current revision 2 as changed.
- Title alternatives were stored separately without replacing the manuscript.
- Resume returned the pending review step and pinned voice; a compact checkpoint could report it without reading all source bodies.

Example checkpoint from that state: “Handoff edit: review; recheck the edited paragraph because proofread is stale. Stop at review. Voice revision 1; source baseline 1, newer source available.” Temporary source/workspace artifacts are excluded from the package. Cross-member and exact guidance restoration remain covered by the existing deterministic suite; no new live GitHub/harness pilot is claimed here.

## Final verification

All 87 tests passed in 55.737 seconds. Full and legacy package validators, immutable-source checks, the token inventory, archive checksums and source equality, and changed-document links passed. Runtime and bootstrap compatibility remain unchanged. M4's deeper review/evidence refinement and M5's independent live Codex/Claude discovery and route pilot remain separate roadmap work.
