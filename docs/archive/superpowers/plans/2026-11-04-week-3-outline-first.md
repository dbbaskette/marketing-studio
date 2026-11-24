# Week 3: Training Studio scan, outline, then targeted research

Authorized scope: #297, after Weeks 1 and 2 merge. Presentation Studio's corresponding flow remains Week 4.

## Contract

New runner-desk trainings pin an outline-first flow in record schema 7, which older runtimes refuse. Schema 6 retains the researched-topics gate. Older records keep their current flow. One bounded Quick-profile scan proposes a provisional editable outline; it supplies no accepted evidence. The person approves exact sections, objectives and research questions before the Harness Research pipeline starts. Materials use that approved outline plus the checked research. The pinned companion protocol remains unchanged.

## Increments

1. Add a bounded provisional-outline schema and validation, a deterministic editable fallback and source-summary input budget. Keep the worker schema and its fixture/guidance/tests together. The scan uses the saved Quick model/effort and at most 180 seconds and a small explicit dollar cap, each constrained by existing step/training limits. Supply bounded document text and names; use no external scan searches, so the hard search cap is zero. Web research remains available after approval under the saved source policy.
2. Insert scan and the existing training-plan decision before research for new outline-first records. Save a usable partial/fallback outline on timeout or stop; do not escalate or run a second outline-writing job automatically. Preserve scan cost/activity and accepted partial output. Old researched topics gates stay as saved.
3. Expose local editing of section titles, objectives and one-to-three questions, section add/remove, and separately listed typed intake questions. Approval binds the edited outline plus intake/source scope. Save edits without assistant work. Reject stale decisions and decisions while a worker is still active or the run remains stopped.
4. Convert approved sections into research-plan items (one section's grouped questions per item), retaining the existing maximum-three-area grouping/concurrency and round limits. Supplied-only stays supplied-only. Write the local research plan after approval, then run existing investigation, synthesis and independent review. Pass approved teaching scope into blueprint/material drafting; never use scan text as evidence.
5. Offer explicit adoption only for stopped, eligible work before accepted research/teaching plans. Show retained and replaced work first. Preserve unfinished research as history rather than claiming reusable checked evidence. Adoption starts no work; Resume training runs the scan. Past-research records and direct saved routes remain unchanged.
6. Update the workflow diagram generator and checked output, Training Studio desk guide/README, research-synthesis documentation and release notes. Name the remaining Presentation Studio and section-review reuse work accurately.

## Transition matrix

| Before | Event | After | Test |
| --- | --- | --- | --- |
| New supplied-only intake | Start | One Quick scan, no deep research | Scripted model/effort/call-count assertions |
| Scan running | Stop or time cap | Saved usable provisional outline; no escalation | Stopped/timeout and reload cases |
| Editable outline | Add/edit/remove sections and questions | Local revision, zero model calls | Exact-revision plan tests |
| Unapproved outline | Poll/reload | Same scope, zero deep calls | Native/API browser checks |
| Approved edited outline | Continue | Only retained sections become research items | Removed-section call-scope assertions |
| Web allowed | Scan then approved research | Zero scan searches; normal approved research scope | Worker tool/permissions assertions |
| Typed intake questions | Scan | Questions retained separately for review | Preservation test |
| Deep research running | Stop/resume | Existing retained work and source policy survive | Research integration checks |
| New outline-first record | Open in an older runtime | Unknown schema refused; no silent research-first drive | Versioned record tests |
| Old training past research | Open/upgrade | Original saved flow | Compatibility fixtures |
| Eligible stopped old training | Explicit adoption | New flow pinned, no job starts until Resume training | Adoption/conflict tests |

## Verification and delivery

Use scripted workers, bounded synthetic inputs, disposable settings/workspaces, and no provider/Google access. Verify the native UI by keyboard at 390 and 1280 pixels in light/dark, plus scan timeout/stop/reload, stale approval and old-flow compatibility. Run the complete relevant Training Studio suite, affected shared checks, package/workflow-diagram validators and installer/CLI acceptance on the final candidate. Publish a Week 3 PR closing #297, pass required gates, merge its exact verified head and record the result.

Delivery: [Week 3 PR #329](https://github.com/dbbaskette/marketing-studio/pull/329). The PR retains the final test evidence and merge status.

Verification completed on runtime tree `c31d1a93ac83ccd9cb475f3c386142f672d05238`: all 3,173 Training Studio tests, package validation, all four independent/shared setup and authenticated launch journeys, the 41-step Hub journey and 39-command shared CLI journey passed in disposable macOS 27/Python 3.13 state. The full shared suite (958 tests), native outline browser at 390/1280 in light/dark, and diagram validation passed on `7e3e778c1ce1ce2f613613b9bf88c57a93ec8048`; subsequent changes repaired a copy assertion and JSON-example budget accounting, leaving the shared/browser application flow unchanged. The VM's one real-PDF intake skip passed separately on the host with actual synthetic PDF bytes for all four studios. Unchanged Presentation Studio, Blog Studio and Infographic Studio retain Week 2's full-suite evidence. All task-owned test VMs and visual-fixture processes were cleaned up; no live providers or Google jobs were used.
