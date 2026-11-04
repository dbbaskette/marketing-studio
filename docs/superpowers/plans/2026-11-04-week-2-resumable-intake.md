# Week 2: resumable intake and content-first desks

Authorized by the audit roadmap and the instruction to implement, push, PR and merge Week 2 after Week 1.

## Functional increments

1. Add a shared private intake-draft store and authenticated native adapters. Reads create nothing. Drafts live under each studio's private data directory, keyed to the configured workspace. Adjacent locking, atomic owner-only files and revision checks protect concurrent tabs. Save/close preserves the draft; explicit discard clears only that draft. No project or job is created by persistence.
2. Add a shared browser intake controller to the existing desk kit. Save field changes serially with coalescing and revision checks. Restore source-draft identity, selected Library revisions, field values and current step. Captured sources remain in the existing source store. Preserve file input bytes where the native form already reads them. Report save failures honestly and guard navigation while a save remains pending.
3. Convert New deck and New training into three actual pages. Back/Next preserve all fields; validate the current page and return to the first invalid page at final confirmation. Keep advanced controls disclosed. The last page names the next operation, selected outputs and the applicable assistant/limits. Existing saved-run and direct deck routes retain their behavior.
4. Align creation sheets and nested pickers through shared tokens: centered, dimmed and opaque forms, consistent width/edges/actions, a visible footer and one primary action. Preserve focus trapping, dismissal and nested-sheet return. Reading and form content remains opaque.
5. Render Library upload rows immediately, update them per file, announce completed/total and current filename. Keep the existing serial uploads and stable operation IDs. Retain failed files for failed-only retry, with successful results preserved. State clearly that navigation waits while an upload is active.
6. Give the shared native server an explicit bounded listen backlog for simultaneous initial script requests. Python-version defaults must not drop an asset burst on a slower machine.
7. Put selected slide/material content early. Keep actionable blockers visible; disclose optional warnings, delivery explanation and repeated readiness instructions with visible counts. Preserve Training Studio's existing compact toolbar and tabs. Check useful reading content within the first 390×844 screen.

## Transition matrix

| Before | Event | After | Verification |
| --- | --- | --- | --- |
| Intake page 1/2 | Next/Back | Other page with all inputs and source pins kept | Native page/browser fixtures |
| Open unfinished intake | Reload | Same page and saved values; zero provider calls | Authenticated draft and browser tests |
| Open intake | Save and close | Private draft retained; no project created | Draft store and native adapter checks |
| Retained draft | Explicit discard | Only intake cleared; captured/library/project files untouched | Isolated store tests |
| Two draft readers | Old reader saves | Conflict; newer values preserved | Revision test |
| Batch upload | First file completes | First outcome visible while later row remains running | Scripted delayed upload browser route |
| Mixed batch complete | Retry | Failed files only, same operation identities | Existing idempotence journey extended |
| Clear desk | Open on phone | Selected content visible; warnings count reachable | 390/1280 browser geometry assertions |

## Verification and delivery

Use disposable workspaces, settings, browser fixtures and scripted providers. Run targeted checks after coherent slices, then the full relevant shared/native suites once on the final candidate. Run native package and CLI acceptance and representative light/dark/reduced-effects browser journeys. Preserve valid Week 1 evidence for unchanged code. Publish one coherent Week 2 PR closing #316, #320, #322 and #323, check required gates, merge the verified head, and record the PR/commit in the roadmap. No provider or Google write is authorized by testing.
