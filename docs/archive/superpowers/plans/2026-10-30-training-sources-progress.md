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

Status: implemented and verified. Source identities and capture permissions are
checked before metadata. A nonconflicting `date` value becomes `source_date`;
conflicting dates, unknown fields and malformed source objects produce corrective
feedback within the current author job. The pinned helper still validates the
evidence and performs the independent review.

Verification used disposable macOS 27 Tart clones and retained valid evidence for
unchanged code. The full shared suite covered 742 cases; three failures exposed
schema-incomplete helper fixtures and validation ordering. Their corrections passed
92 affected checks. Blog Studio's 1,640 cases passed. Presentation Studio's 2,071
cases ran, with its corrected worker fixture passing both affected cases and its
package validator. Training Studio's 3,012 cases ran; the retired wording assertion
was updated and both affected naming cases and package validation passed.
Infographic Studio's 185 cases passed with seven optional renderer/PDF cases skipped;
its real-renderer research browser journey and real PDF capture/preview across all
four studios passed separately.

Real browser journeys passed upload → Start → topics review without another intake,
topics changes and automatic generation, and explicit Infographic Studio research
import. They covered progress-only refreshes, retained disclosure/focus, keyboard
scrolling above phone navigation, 320–1280px layouts and light/dark appearances.
All four native setup/authenticated-launch checks passed, plus the 41-step Team Hub
journey and 39 CLI command checks. Owned test VMs were removed. No personal training,
provider job, app installation or running service was changed.
