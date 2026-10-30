# Training Studio: one source handoff and readable research progress

The new-training form already captures selected documents privately and validates
their revision on Start. Training Studio must recognize those captures without
asking the person to upload or confirm them again. Preserve legacy document intake,
permission choices, source hashes, restart/retry identity and existing approvals.

The research screen uses one opaque progress surface with its actual phase,
three labelled research stages, measured time, and compact investigation summaries.
Full questions remain in native disclosures; completed and failed areas retain
distinct words/shapes. Stop training belongs in that surface. Keep the existing
system typography, neutral paper/canvas and studio accent tokens; add no libraries,
background animation, inferred completion percentages or assistant requests.
Desktop investigations share a row; phones stack them. Disclosures, focus,
long questions, dark mode and reduced effects remain usable across refreshes.

| Input/state | Expected transition | Verification |
| --- | --- | --- |
| Validated captures on Start | Research can begin; no second document prompt | Native engine and real-page start |
| External search with no captures | Start without a document confirmation | Native engine and browser |
| Legacy file upload | Keep add/done recovery and permission checks | Existing document suite |
| Captured source missing or changed before research | Refuse using it; never silently fall back to public search | Native engine |
| Same form retried | Return the same training with retained captures | Existing start receipt test |
| New or old source-backed run with confirmed captures | Resume recognizes local verified inputs without another upload | Native engine |
| Investigating/combining/checking | Show actual phase; only measured completion is shown | Shared component and browser |
| Paused/stopped/failure/complete | Clear status; retain evidence and real available controls | Shared component and browser |
| Polling a question disclosure | Keep its open state and focus | Real page/browser |
| Only research phase/timing changes | Redraw the progress view without waiting for another training state change | Real page/browser |
| Source metadata uses date | Preserve a nonconflicting date as the pinned source_date field before helper collection | Pinned native helper |
| Unknown fields or conflicting source dates | Return corrective feedback inside the current worker job; never silently discard metadata | Native submission/unit cases |
| Phone keyboard reaches timing disclosure | Keep focus above fixed navigation | Real browser |

Verification uses synthetic sources, settings and workers only. Run affected
engine/component checks after the full slice, then the complete suite through the
existing Tart runner. The source-metadata correction affects the shared research
boundary, so include all four native studios. Do not restart or modify the
person's active training.

Status: implementation in progress.
