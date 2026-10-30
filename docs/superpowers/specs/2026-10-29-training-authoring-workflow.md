# Training Studio: review the topics, then build the training

Status: implemented and verified; one lightweight review and automatic generation.

## Outcome

Training Studio does the research, planning and writing. It shows **Here’s what
this training will cover**, with topics, order, depth, timing and planned examples
or exercises. The person chooses **Ask for changes** or **Build the training**.
Build generates all selected materials. No sample lesson or extra teaching-brief
interview is required. Existing Blog Studio editing patterns remain available
for changes to the resulting materials.

## Implementation boundary

Reuse the existing researched and validated blueprints as the topics overview;
there is no second outline author job or new teaching document format. Combine
all selected levels into one review before writing guides, briefs, practice or
slide content. The person can request more depth, different emphasis, practical
work or changes to coverage in a short note. Revising the plan does not repeat
research. Preserve earlier versions and keep the exact current plan visible.

The agreed topics drive guide, brief, deck and scenario writers through their
existing blueprint inputs. Level labels are starting suggestions: the person's
explicit task, audience and desired depth govern what is taught.

New Training Studio runs have one development checkpoint. After topics approval,
slide content is drafted and designed automatically through the existing native
flow; no second default slide-text approval is inserted. The separate Presentation
Studio workflow is unchanged. Real missing inputs, limits, companion-required
questions and final readiness/delivery retain their existing controls. Approval
of the topics never marks the finished materials Ready or publishes them.

## Interface

While preparing topics, show research/planning progress and source problems.
While waiting, show one opaque topics review with one primary Build action.
Hide premature delivery/finishing controls and empty material placeholders.
Examples, exercises and evidence gaps can be expanded. Keep typed notes and
keyboard focus across polling; label the current level and preserve phone layout.
After Build, return to the existing editable material desk as work is produced.

## State and compatibility

Save the new workflow as runner schema 6 so an older runtime refuses to drive it
rather than silently skipping its decision. Existing saved runs keep their own
flow. Decisions bind to intake and blueprint hashes plus a monotonically advanced
review revision; duplicate change requests cannot silently repeat work even if
an author returns identical wording. Reject changed versions, foreign ownership,
active work and paused/failed decisions before changing anything.

A read or restart starts no migration and grants no approval. Source scope,
Google permissions, shared settings, assistant allowance and worker capacity are
unchanged. Research and slides remain delegated to their companion skills.

## Acceptance

- All levels appear in one topics review before any material or image work.
- A note reaches the plan writer and revises only plans; research is retained.
- Build generates the selected materials without a sample lesson or another
  default slide-text stop in Training Studio.
- Missing notes, unauthenticated requests, changed versions, duplicate requests
  and unsafe file paths are refused without dispatching work.
- Plan acceptance remains distinct from finished-material readiness and delivery.
- Old runs and Presentation Studio keep their existing behavior.
- Actual native page journeys work at phone/desktop widths with synthetic authors;
  verification makes no live provider quality or timing claim.
