# Training Studio: useful materials with fewer decisions

Scope: refine the existing training engine, page and companion handoffs. No new
provider, publishing action, shared setting, installation or external write.

## Product contract

Start with the learner's task and audience, then choose the materials needed.
Research and the teaching blueprint remain the common foundation. A learner
guide, reference brief, slide deck and practice scenarios are independently
selectable. Yoodli remains an optional preparation format requiring a brief and
practice scenarios. Existing forms/runs retain their current selections.

Keep sources prominent. Put levels, brand details, extra copies and assistant
settings behind relevant disclosures. Before starting, summarize the materials,
source permission and actual shared review policy. Never promise manual gates
that the selected policy continues automatically.

While working, show the next useful action, completed materials and then optional
production detail. Reading a document or expanding details approves nothing.

## Instruction contracts

- Harness Research owns investigation and review. Preserve audience, training
  purpose, selected source permission, scope, versions, counterfacts and gaps.
- The blueprint connects observable objectives to explanations, worked examples,
  checks and practice. Unsupported points stay out of teaching.
- Harness Slides owns composition, rendering and visual review. The training
  handoff carries objective/assessment alignment, module timing, evidence limits
  and selected practice. Treat timing as a teaching judgment, not a universal
  two-minutes-per-slide rule.
- Illustrative exercises may be authored, but must be labeled hypothetical and
  cannot invent product capabilities, customer results or evidence. Answer keys
  explain why an answer is right and why a plausible alternative is wrong.

## Implementation and verification

1. Add validated material selection using existing per-stage skip decisions.
   Preserve legacy defaults, validate Yoodli dependencies and calculate manual
   gate counts from actual selected stages. Exercise guide-only, deck-only,
   practice-only and full-bundle paths with disposable engine fixtures.
2. Refine the three setup steps, accurate review preview and run-detail
   disclosure. Exercise real page wiring, narrow layouts, focus and failure.
3. Align worker and conversational handoffs and teaching-quality guidance.
   Check package disclosure budgets without raising them. Test saved handoff
   content and context propagation; do not equate structural checks with
   instructional effectiveness.
4. Run the complete Training Studio suite through the shared Tart runner once
   the end-to-end slice is stable. Use synthetic providers and preserve logs.

## State-transition matrix

| Input/action | Before | After | Evidence |
| --- | --- | --- | --- |
| Legacy form omits materials | Not started | Existing guide/brief/practice defaults | Form compatibility regression |
| Explicit materials | Not started | Only selected stages, with page skip decisions | Form/create and engine journeys |
| No material or deck selected | Not started | Refused; no folder/run made | Form/API regression |
| Yoodli without brief or practice | Not started | Refused; answers kept | Form/page regressions |
| Unselected optional stage | Foundation approved | No worker or gate for that stage | Pipeline/engine regression |
| Disclosure/read navigation | Any saved state | No approval or job started | Page wiring regression |
| Shared review preview | Before start | Describes current policy; run snapshots it | UI policy cases |
| Shared review changed after preview | Not started | Refused before creating files; reload preference with answers kept | Engine/page regression |
| New source/blueprint revision | Approved derived output | Existing stale/rebuild behavior | Reuse existing lineage suite |
| Confirm a runner gate or slide-direction approval | Reading the reviewed version | Return to the same training, announce success; no second navigation dialog | Gate and outline page journeys |
| Grouped review | Waiting for direction or final review | One persistent toolbar approval with the displayed revision | Grouped approval/refusal regression |
| Edit a grouped change request, then refresh or fail | Unsaved request text | Keep the text for that training, phase and material; show refusal beside the request | Grouped revision refresh regression |
| Refresh a review while reading | Expanded and collapsed sections chosen by the reader | Preserve both disclosure states | Grouped disclosure regression and phone walkthrough |
| Enter final grouped review | Finished materials and supporting records | Materials first, first material expanded; research and planning still available | Final-review ordering regression |
| Open finished training, including a teammate's | Ready to use | Index action stays in the toolbar while reading | Finished and team page journeys |

## Yoodli extraction decision

Recommend a separate optional `harness-yoodli` skill, delivered in a later release.
It should own platform-specific field mapping, sourced capability profiles,
character counts, criterion-to-goal checks and copy-ready builder handoff. Training
Studio should own learning objectives, approved scenarios, evidence, user review
and package readiness. Generic practice must work without Yoodli.

The first standalone skill should accept an approved scenario, knowledge brief,
objective/rubric mapping and output directory. Return a versioned manifest with
input digests, profile provenance, checks, field blocks and unresolved needs.
Support standalone scenarios without requiring a whole course. Pin a capability
version per existing training; migrate explicitly and keep the embedded adapter
until compatibility is verified. Do not introduce an unavailable dependency now.

Release in two increments: a standalone authoring/validation skill first, then
an explicitly pinned Training Studio adapter. Keep one owner for platform facts
and limits; the adapter must not fork the profile or validators. The shared
installer can offer the companion later, without a second installer framework.
Require compatibility fixtures for all four practice modes, unchanged older
trainings, over-limit fields, missing knowledge files, incomplete criterion
coverage and a standalone scenario without a training directory. A manifest
must distinguish a prepared handoff from a roleplay actually created in Yoodli.

No claim of automatic Yoodli upload/import: the current integration prepares
copy-ready fields. Official documentation distinguishes Roleplay Agent from the
Builder: the agent creates new roleplays but cannot edit existing ones or create
new custom goals. AI Assets and custom goals have their own account requirements.
Keep any future platform automation separately authorized and capability-checked.

Sources checked 2026-10-20:

- [Roleplay Agent](https://support.yoodli.ai/en/articles/15960287-create-roleplays-with-roleplay-agent)
- [AI Assets](https://support.yoodli.ai/en/articles/16054213-add-ai-assets-to-a-roleplay)
- [Custom goals](https://support.yoodli.ai/en/articles/11556965-creating-custom-goals)
