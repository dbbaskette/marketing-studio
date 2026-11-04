# Marketing Studio audit implementation roadmap

Status: Weeks 1–3 authorized for implementation, verification, PR publication and merge.
Basis: audit tracker [#326](https://github.com/dbbaskette/marketing-studio/issues/326), checked 2026-11-04.
Scope: all 14 new audit issues (#312–#325), plus existing #297 and #305. #326 is the tracking/closure issue.

## Delivery contract

Use a bounded Quick-model scan to propose editable scope before deep research. Keep the accepted evidence and completed build units. Editing or retrying affects only units whose inputs changed. Final consistency checks and exact-revision human approval remain explicit. Existing direct paths for finished scripts and notes-only changes remain available.

Plan approximately eight weeks for one primary implementer with AI assistance, including an integration/buffer week. These are effort estimates, not provider speed or completion guarantees. Re-estimate after Week 1's companion-contract check. Schedule starts when implementation is authorized.

Each weekly cohort should produce independently reviewable changes; do not use one eight-week branch. Prefer 1–3 coherent PRs per cohort, split by durable behavior rather than by file or tiny mechanical task. Branch/commit/PR publication follows the user's actual instructions.

## Groups and schedule

| When | Group | Issues | Demonstrable outcome |
| --- | --- | --- | --- |
| Week 1 | Editing reliability and measurement | #312, #313, #314, #319 | Continuous typing works; Library confirmation stays visible; source focus is retained; first-useful-result timing can be measured. |
| Week 2 | Shorter intake and calmer appearance | #316, #320, #322, #323 | Resumable real intake steps, progressive upload results, content-first desks and consistent sheets/actions. |
| Week 3 | Training Studio outline-first | #297 | Quick scan → editable teaching outline → approval → research approved sections; partial scans remain useful. |
| Week 4 | Presentation Studio outline-first | #315 | Quick scan → agreed slide story → targeted research → text approval → design, retaining direct script/edit routes. |
| Week 5 | Durable research and economical checking | #305, #318 | Completed synthesis/check units survive failure; retries affect unfinished units; identical validated saves preserve eligible review evidence. |
| Week 6 | Scoped changes across outputs | #317, #325 | Change-impact preview names affected research/materials/slides; unchanged verified work is reusable across studio/companion boundaries. |
| Week 7 | Recovery and direct resume | #324, #321 | Partial infographic failure retries the failed stage; home links directly to work needing attention without starting studios. |
| Week 8 | Integration, documentation and buffer | #326 | Cross-studio acceptance, complete appearance/accessibility matrix, full relevant suite, known limitations and final issue evidence. |

### Week 1: editing reliability and measurement

Primary owner: shared browser UI / Marketing Studio implementer.

Files/interfaces: Presentation Studio desk app.js and deck-desk.js; core/studio_core/deck_web/library.js; ui-kit/research.js; core/studio_core/step_times.py; ui-kit/activity.js and existing studio activity adapters.

- Fix focus/caret/node continuity through the first dirty transition, autosave and polling (#312). Include title/point/notes fields and composition input.
- Keep Library selected count/confirmation/cancel reachable at both ends of a long list and clear of bottom navigation (#313).
- Define a successful source-capture focus destination rather than trying to restore a removed control (#314).
- Extend existing timing to separate queue, model, first saved useful result, checks and person-wait time (#319). Use comparable measured ranges, never invented ETAs.
- Perform a bounded companion feasibility check: can the supported Harness Research protocol represent section results/checks for #305, and can Harness Slides expose reusable inspection evidence for #325? Document required capabilities and release boundaries before dependent implementation. Do not edit installed skill copies.
- Verify #297's merged prerequisites remain available: #294, #295 and #296 are closed as of planning.

Milestone: real keyboard typing across save/poll boundaries; selected Library action visible at 320/390/1280 px; source focus retained; scripted timing distinguishes first result from full completion. No live provider needed.

### Week 2: shorter intake and calmer appearance

Primary owner: shared UI implementer; this cohort follows Week 1's focus/sheet fixes.

Files/interfaces: ui-kit/style.css; core/studio_core/deck_web/library.js; core/studio_core/setup_web/app.js; native Presentation Studio and Training Studio desk applications; Infographic Studio runner/web/app.js.

- Establish the shared creation-sheet geometry, footer and primary-action rules once (#323), then apply them with actual intake steps (#316).
- Separate intake draft persistence from jobs and project initialization; restore fields, selected source revisions and navigation on reload. Explicit discard must be clear and confined to the draft.
- Keep costs/next operation clear at the final step. Advanced options remain available without filling the initial view.
- Report each uploaded file as it completes; keep idempotent operation identities and failed-only retry (#320). Bounded parallel upload is optional only if profiling supports it.
- Bring selected slide/document content earlier; preserve visible blockers while condensing optional warnings and repeated instructions (#322).

Milestone: complete/revisit/reload intake without model work or lost sources; first batch result appears before the last file; readable selected content is visible on a phone. Capture a light/dark/reduced-effects reference set for later cohorts.

### Week 3: Training Studio outline-first

Primary owner: Training Studio pipeline implementer.

Files/interfaces: studios/training/runner/engine.py and training_plan.py; shared model_profiles.py, research_session.py and research_transport.py; native training intake/plan UI; existing training plan tests and real-browser fixtures.

- Preserve current saved-work routes. New work pins the chosen flow; adopting a new flow on existing work remains explicit.
- Route the scan through Quick, including explicit model/effort selection and bounded input/time/cost.
- Scan output maps source coverage and gaps, and produces editable objectives/sections/research questions.
- The scan is provisional; it never substitutes for checked evidence.
- Only approved sections become research scope, retaining typed questions and source permissions.
- Save partial/finished results and allow stop/resume throughout.

Proposed initial product target, to calibrate rather than promise: a useful outline in roughly 60–90 seconds for a representative small fixture; a hard scan cap of at most the issue's proposed three minutes. A timeout yields an editable incomplete result rather than automatic escalation.

Milestone: remove a section and prove via scripted call counts that no deep work covers it; no main research before approval; scan timeout/reload/stop preserve usable work.

### Week 4: Presentation Studio outline-first

Primary owner: Presentation Studio pipeline implementer.

Files/interfaces: studios/presentation/runner/engine.py; shared model_profiles.py/research_transport.py; Presentation Studio desk app.js/deck-desk.js and existing intake/outline tests.

Depend on Week 3's stable shared scan/evidence interfaces, not on copying the Training Studio workflow wholesale.

- Reuse the bounded scan mechanism; keep slide-story semantics in Presentation Studio.
- Agree audience, takeaway and slide story before targeted research.
- Retain slide-text, look and final delivery decisions.
- A finished script and a selected edit keep their direct route and do not trigger unnecessary scan/research.
- Preserve scope and completed evidence on retry.

Milestone: new idea follows approved scope; script skips unnecessary jobs; small wording/notes edits make zero evidence-collection calls.

### Week 5: durable research and economical checking

Primary owner: shared research integration / Harness Research implementer.

Files/interfaces: core/studio_core/research_session.py, research_transport.py, model_profiles.py; Training Studio engine; canonical Harness Research synthesis save/review contract. Companion source repository/release owner is resolved during Week 1; installed helper paths are reference evidence, not edit targets.

Dependencies: #297 must merge before #305, as the existing issue requires. Parallel/section checks must fit the supported companion protocol. If a new capability is needed, implement and verify it in its own canonical component before requiring it in the studios.

- Synthesize/check approved sections with existing bounded concurrency; keep completed sections and retry only unfinished ones (#305).
- Give each phase suitable model routing, context and limits without changing explicit saved choices.
- Make unchanged saves idempotent only when all evidence, scope, context and independence identities match (#318). Changed sources/claims/protocols must invalidate appropriately.
- Show per-section progress using Week 1's timing.
- Test protocol compatibility with the pinned real helper and synthetic inputs, not only mocks.

Milestone: inject a timeout in one of four sections; the other three survive; retry calls only the unfinished section; final assembled evidence passes the supported independent verification.

### Week 6: scoped changes across outputs

Primary owner: shared pipeline/Harness Slides integration implementer.

Files/interfaces: studio engines; shared research/evidence records; Presentation Studio runner/steps/build.py and desk UI; canonical Harness Slides review receipts.

Dependencies: Week 5's stable saved research units and companion contracts.

- Before a broad refresh, show changed inputs and affected sections/materials/slides (#317).
- Preserve and expose existing section redraw, notes-only save and unchanged-slide verification capabilities.
- Align the companion's per-slide inspection reuse with the studio's existing reusable_review logic (#325).
- Invalidation covers source bytes/permissions, audience, brand, fonts, order, neighbors, renderer, review questions and final deck consistency.
- Reuse evidence, never carry forward user approval merely because a rendered image is unchanged.

Milestone: an input relevant only to section B leaves A's research/build unchanged; one-slide edits in a 30-slide deck inspect the required changed scope and consistency dependencies; final readiness still binds the exact delivered revision.

### Week 7: recovery and direct resume

Primary owner: Marketing Studio metadata / Infographic Studio workflow implementer.

Files/interfaces: marketing_studio/page.py and bounded native metadata adapters; shared setup home UI; studios/infographic/runner/server.py, engine.py, activity.py and web/app.js.

- Return safe failed-substep/completed-substep/next-action information and retry only the failed local operation (#324). Preserve artwork and uncertain remote-request identity.
- Show Needs you/In progress/Recent work with direct resume links (#321).
- Read home metadata with bounded cost; never start studios, initialize workspaces or read whole content trees just to populate a summary.
- Preserve current source, history and delivery receipts through reconnect and partial failure.

Milestone: failed preview retries no assistant/image operation; home resumes the exact pending decision without side effects; missing/offline workspaces report honest status.

### Week 8: integration, documentation and buffer

Primary owner: one integration/verification owner.

- Run complete cross-studio scripted journeys on the final candidate, including supported old saved flows.
- Complete 320/390/1280 px, light/dark, keyboard, 200% zoom and reduced-effects checks; no unsupported claim of mobile keyboard or screen-reader acceptance.
- Compare time to first useful result, assistant call counts, retries, render calls and affected-work counts against the recorded fixtures. Distinguish synthetic timings from real-provider results.
- Update workflow diagrams, setup/help, compatibility notes and relevant CHANGELOGs with the final implemented behavior.
- Run the existing complete relevant Tart suite and native/package acceptance once on the final integrated candidate. Reuse valid unchanged-tree evidence and repeat affected checks after any correction; retain required component/CI gates.
- Close #326 only when its issues are resolved or explicitly recorded as remaining scope. A local pass is not provider or release acceptance.

## Dependencies and related backlog

Critical path: #297 → #305 → #317. #315 can use the shared scan contract after #297. #325's verified companion contract must be available before #317 claims complete cross-component reuse. #318 can be developed independently once the identities/contract are defined. Early #319 supplies measurement to later cohorts.

Do not keep every change blocked behind the critical path: focus fixes, Library confirmation, upload feedback, reading hierarchy and sheet styling can land independently.

Related existing issues, outside the 16-item audit implementation estimate:

- #308: small CLI running-instance fix; sensible Week 1 companion PR if capacity allows.
- #304: spending-limit policy; schedule after #297 (Week 5 is suitable). Keep per-job caps, explicit hard-stop choices and old-project compatibility. Treat as policy work, not a silent side effect of performance changes.
- #224: pair its remaining UI/export recovery work with Week 7. It also owns first-release readiness and depends on #152/#223/#225 and separately authorized live-provider acceptance; do not promise full closure in this eight-week audit schedule without sizing those prerequisites.

## Verification ownership and review focus

Implementers own focused behavior checks and the required relevant component suite before marking their changes complete. A single integration owner owns the final cross-studio full run and evidence index; reviewers do not each repeat the same full suite. Reuse valid evidence for unchanged code and environment.

Review the cross-boundary risks explicitly: stale scope/approval, duplicate provider requests, evidence reuse after changed inputs, pending unsaved edits, concurrent settings updates, stop/retry/reconnect, old saved tasks and local-only home browsing.

All verification uses disposable state and scripted providers. Paid-provider work, Google writes, deployment and user upgrades remain separate actions. The user authorized implementation, PR publication and merge for Weeks 1–3.

## Completion record

- [x] Read audit tracker and current dependencies.
- [x] Confirm #294–#296 are closed and #297/#305 plus #312–#325 remain open.
- [x] Map every audit implementation issue to a cohort.
- [x] User authorizes Weeks 1–3, each through PR publication and merge.
- [ ] Record cohort PRs, tested tree, evidence and actual effort as work completes.

