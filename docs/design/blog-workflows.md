# Blog Studio workflows

## Outcome

The main interface follows a writer's task from starting material to a useful
result. Editing an existing manuscript stays on one workflow; users do not
approve an internal review artifact before choosing edits.

## Paths

| Job | Steps | Result |
| --- | --- | --- |
| Polish a document | Choose Google Doc, pasted text, or a file → polish → choose changes → finish | Google feedback or a revised local draft with retained history |
| Write from a brief | Brief and audience → optional sources → outline → draft | A saved manuscript ready for editing or download |
| Write from an outline | Brief and supplied outline → optional sources → draft | A draft guided by the supplied structure |
| Explore ideas | Brief → three angles → select and develop | An outline/draft from the chosen angle |

## Interface contract

Home offers tasks and a compact resume list. Polish a document asks for the
input method: Google Doc link, pasted text, or an uploaded text/Markdown/Word/PDF
file. These are source choices within one task, rather than separate workflows. Blogs open the relevant next step.
The editor has three explicit steps: Choose task, Review changes, Finish.
Polish combines proofreading, copy editing and natural wording, without research.
Fact checking, structure review and scoped revision remain available under other
editing actions. Evidence and provider details use progressive disclosure.

Review changes shows original, proposed replacement and reason together. Users
can use all proposed changes in one click or select a batch, then continue. Local application and Google sending remain
separate choices. The Finish screen automatically checks Google and previews the target and selected changes,
requires an explicit send, and reports verified, pending or uncertain outcomes.
Repeated delivery checks use the existing receipt rather than resending.
Stale feedback cannot be silently selected or sent. Manual quoted feedback and
raw manuscript editing remain available as secondary tools.

Active and failed editing operations stay in the editor, with progress, stop,
retry and a clear route back to the draft. The editor refreshes when operation
state changes without replacing unsaved text. Existing focused-review links
redirect to the editor. New-writing gates retain their decisions with concrete
labels and the next result explained; detailed stages/history are secondary.

## Implementation and verification

Reuse the authenticated API, existing worker, optimistic tokens, source permissions,
local history, team locks and Google delivery helper. Add only presentation state
needed to resume editing and a guarded batch application for local suggestions.
Use the existing upload-as-blog endpoint for uploaded or pasted manuscripts.

Implement entry points and drafting flow, then the editor/review/finish slice.
Verify task navigation, no-research polishing, batch selection and local apply,
stale/active refusal, Google preview/send/retry, recovery from failure and unsaved
text retention with synthetic documents and providers. Walk the browser at phone
and desktop sizes. Run the full relevant suite and synthetic CLI acceptance through
the existing Tart runner. Preserve real workspaces and do not run live providers.
