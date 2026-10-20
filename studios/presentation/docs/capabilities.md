# Presentation Studio capability coverage

The installed `studio` CLI has `serve` and read-only `status`; drafting operations
run through the same engine as the browser. Worker tools are internal validated
contracts, not additional person-facing CLI commands. The conversation skill
uses companion commands and the same readable deck records.

| Task | Browser entry point | Engine or command |
| --- | --- | --- |
| Start from an idea, document, or existing deck | New deck | `Engine.start` |
| Choose preservation scope and selected slides | New deck → What changes | `decks.check_form` |
| Import a conversation-created deck | Decks → Bring in a deck | `Engine.bring`; remembered decks only |
| Review research, classify, revise and approve | Current deck checkpoint | `Engine.decide` and item marks |
| Retitle, reorder, add or remove outline slides | Outline review | `outline.apply_edits` |
| Preview a visual storyboard, including unsaved edits | Automatically at Outline; Preview storyboard refreshes edits | Harness Slides `outline draft` |
| Confirm identity or change brand | Direction/brand review | Saved contract and cover preview |
| Request the first native draft before AI critique | New deck → First native build | Run-scoped `initial_review` |
| Inspect native slides, partial previews and findings | Current deck | `Engine.picture`, build progress |
| Send revision-bound feedback during section construction | Partial slide preview | `Engine.build_feedback` |
| Review an unreviewed first draft | Run AI review | `Engine.review_draft` |
| Accept or revise an unreviewed draft | Use/export draft as-is; Ask for changes | Actual user decision; AI status stays separate |
| Pause, stop, resume, retry or undo | Current deck toolbar | `Engine.act` |
| Answer a worker question | Current deck question | `Engine.answer` |
| Read saved intake, outline and research files | Saved inputs, outline and run details | Authenticated bounded `/api/file` |
| Inspect requested model routing and reported actual model | Saved inputs, outline and run details | Run-scoped model receipts |
| Download PowerPoint or deliver to Google Slides | Finished deck | Exact native artifact; `Engine.download` / `deliver_again` |
| Share, fetch, take or hand over | Sharing controls and deck ownership | Existing Git workspace operations |
| Record numbered team revisions | Finished deck → Publish; Decks → Published | `Engine.publish` / `published`; no public CMS write |
| Delete a deck with a preview of retained work | Current deck → Delete | `Engine.leaving` / `delete` |
| Setup, models, budgets, notifications and release checks | Settings and Status | Existing settings/upkeep APIs |
| Read setup and deck status without serving | Status; terminal `studio status` | No provider jobs |

Installation, rollback and removal remain explicit installer operations. Rehearsal
is not implemented by either route and is labeled as future work. Native Google
and assistant acceptance requires a signed-in destination; fixture checks do not
establish that provider coverage.

A storyboard proposes wording and structure, not final artwork. Its HTML is shown
in a script-disabled, opaque-origin sandbox with no network access. New preview
requests include a source fingerprint; they save no writing or approval.

Progress polls once per second while an open deck is working; hidden pages use
the slower background pace. The local display cache records first section ready,
first loaded section image, first whole preview and final review/draft-ready
times separately. Loading a picture records a display measurement, not approval.
Native render fingerprints allow clear unchanged slide inspections to carry
forward only when dependencies, pixels and order match. Changed slides and
neighbors receive full-size inspection and the current whole-deck contact sheet
is checked again. Older renderers without evidence receive full fresh review.
Critique packets retain complete slide coverage and reuse provenance.
