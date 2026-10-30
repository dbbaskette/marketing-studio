# Shared slide text before design

Training Studio and Presentation Studio use the same default new-deck journey:
write slide text, ask for changes or approve the exact text, then design and render.
This follows the requested workflow; no research, slide-building or brand logic is
moved out of the companion skills.

## Contract and implementation

1. Save a versioned content-first marker on newly started desk runs. A shared
   checkpoint helper holds each deck's existing outline decision. Older saved runs
   and explicitly requested per-slide design walkthroughs keep their contracts.
2. Reuse the validated outline as the text draft: slide title, visible copy, order
   and speaker notes. The text task does no layout composition, asset generation,
   look sample rendering or visual review.
3. Render one shared opaque content-review component in both desks. The person can
   request text changes or choose **Approve text & design deck**. Changes stay at
   the text stop; design starts only on explicit approval. Notes remain editable
   across polling. Keep existing final readiness/delivery decisions.
4. Use the native authenticated decision endpoints and exact version guards.
   Permit only this content decision through the desk's existing gate boundary;
   other desk decisions retain their original routes. Ignore repeated old approvals.
5. Centralize the visual review wire adapter. Only after inspection, translate the
   reviewer's negative findings into the full slide/question answer matrix required
   by current Harness Slides. Every false answer matches a finding. Legacy schema-1
   packets keep their old wire shape. Keep rendered review independent from text
   approval; a formatting failure never means the text failed its quality review.

## State-transition matrix

| Trigger | Result | Evidence |
| --- | --- | --- |
| New desk outline saved | Wait for slide text approval; no look/render/section job | Both native journey tests |
| Ask for text changes | Revise words, return to text review; no drawing | Both native journey tests |
| Approve exact current text | Existing look/design/build flow resumes | Both native journey tests |
| Missing/changed version | Refuse; no drawing | Native engine and authenticated page checks |
| Duplicate approval | Native waiting-state guard refuses old decision | Existing native decision guards |
| Old saved run / explicit design walkthrough | Retain original gates and work | Historical fixture suites |
| Current rendered review submitted | Full matrix, exact slide inventory and findings | Shared bridge and Training Studio regression |
| Current critic after a partial redraw | Inspect full render and supersede older peer findings; never invent uninspected passes | Training Studio repair regression |
| Old rendered review submitted | Legacy packet payload retained | Bridge and native suites |

## Verification

Use disposable source/workspace/settings/Git identities and synthetic authors.
Run targeted native journey and adapter regressions together, then the complete
Marketing Studio/shared core, Training Studio and Presentation Studio suites in a
shared-runner Tart guest. Reuse unaffected prior Blog Studio/Infographic Studio
suite evidence, with the shared kit's complete DOM checks and Blog Studio page
checks. Inspect the shared content view at phone and desktop sizes. Run package
validation and the existing native CLI/Hub acceptance journeys. No provider jobs,
Google writes or automatic repair of an active saved training during verification.

No speed claim is made before measurement: this removes design/render work from
the text phase, but source length and the configured assistant still affect time.
Publication and active installation/restart remain separate actions.

## Completion

Implemented the shared content-first checkpoint, common review component and
current/legacy critic wire adapter. Both native journeys cover text changes,
exact-version approval and no early design/render. Current Training Studio critic
packets after partial redraws receive a whole-render inspection; legacy packets
retain their original scoped-review contract.

Complete affected suites were exercised in disposable macOS guests, with affected
checks rerun after correcting the reported response/progress compatibility issues.
The shared kit DOM suite, phone/desktop browser controls, package validation and
native setup/launch/CLI/Hub journeys pass. A direct check against current Harness
Slides reproduces the original refusal with the old payload and accepts the shared
adapter payload. Synthetic fixtures only; no live provider quality or duration
claim. Saved runs were not reset or retried during verification.
