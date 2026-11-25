# Presentation Studio capability coverage

The installed `studio` CLI has `serve` and the read-only `status` and `saved-work`; drafting operations
run through the same engine as the browser. Worker tools are internal validated
contracts, not additional person-facing CLI commands. The conversation skill
uses companion commands and the same readable deck records.

| Task | Browser entry point | Engine or command |
| --- | --- | --- |
| Start from an idea, document, or existing deck | New deck | `Engine.start` |
| Choose preservation scope and selected slides | New deck → 2. Your deck and what changes | `decks.check_form` |
| Import a conversation-created deck | Decks → Bring in a deck → Bring it in | `Engine.bring`; remembered decks only |
| Approve the slide story and the slide text | The deck's progress → Approve story & research; Approve text & design deck | `slide_story.decide`; `Engine.decide` (the content-first slide text) |
| Retitle, reorder, add or remove outline slides | Desk → Outline tab | `Engine.desk_outline` (`outline.apply_edits`) |
| Read a document the other way | Desk | `Engine.desk_reread` |
| Choose the look, or draw the looks again | The deck's progress → Pick the look; Desk → Change the look | `Engine.desk_look` / `desk_look_again` |
| Open a deck the earlier step-by-step flow saved, or read it | Its saved record → Open on the desk (a preview, then Apply); Saved files | `desk_migration`; the finished Open on the desk; authenticated `/api/file` |
| See the first draft before the deck is checked | New deck → How it looks → Options → See the first draft before the deck is checked | Run-scoped `initial_review` |
| Inspect native slides, partial previews and findings | Current deck | `Engine.picture`, build progress |
| Send revision-bound feedback during section construction | Partial slide preview | `Engine.build_feedback` |
| Note a slide, or the whole deck, and have only their parts drawn again | Desk | `Engine.desk_note` / `desk_deck_note` |
| Pause, stop, resume, retry or undo | Current deck → More, and its stop | `Engine.act` |
| Answer a worker question | Current deck question | `Engine.answer` |
| Read saved intake, outline and research files | Saved inputs, outline and run details | Authenticated bounded `/api/file` |
| Inspect requested model routing and reported actual model | Saved inputs, outline and run details | Run-scoped model receipts |
| Download PowerPoint or send it to Google Slides | Finished deck → Download .pptx; Send to Google Slides | The exact native file; `Engine.download` / `deliver_again` |
| Share, fetch, take or hand over | Sharing controls and deck ownership | Existing Git workspace operations |
| Record numbered team revisions | Finished deck → Publish; Decks → Published | `Engine.publish` / `published`; no public CMS write |
| Delete a deck with a preview of retained work | Current deck → Delete; Delete on each deck in Home and Decks | `Engine.leaving` / `delete` |
| Setup, models, limits, notifications and release checks | Settings and Status | Existing settings/upkeep APIs |
| Read setup and deck status without serving | Status; terminal `studio status` | No provider jobs |
| List the saved decks that still need an older path | Terminal `studio saved-work [--folder PATH]` | `Engine.saved_work`; read-only, no provider jobs |

Installation, rollback and removal remain explicit installer operations. Native Google
and assistant acceptance requires a signed-in destination; fixture checks do not
establish that provider coverage.

A deck the earlier step-by-step flow saved is a saved record: nothing continues it
(GitHub issue #542). It opens on the desk through the explicit migration, or through the
finished Open on the desk once delivered; it waits, saying for what, while a step is in
hand, another computer runs it or its shared files are not committed; or it is read-only
with its reason, and new work starts from it.

Progress polls once per second while an open deck is working; hidden pages use
the slower background pace. The local display cache records first section ready,
first loaded section image, first whole preview and final review/draft-ready
times separately. Loading a picture records a display measurement, not approval.
Native render fingerprints allow clear unchanged slide inspections to carry
forward only when dependencies, pixels and order match. Changed slides and
neighbors receive full-size inspection and the current whole-deck contact sheet
is checked again. Older renderers without evidence receive full fresh review.
Critique packets retain complete slide coverage and reuse provenance.
