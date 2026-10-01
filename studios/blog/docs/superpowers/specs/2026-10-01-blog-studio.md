# Blog Studio skill design

Approved in chat on October 1, 2026: implement the proposed conversational blog
workflow using skills and portable saved files, reusing the five collected
upstream modules and BlogForge's writing capabilities.

## Outcome

One self-contained `blog-studio` entry point offers or infers six starting paths:
existing manuscript, first draft, outline only, draft from outline, author
interview, and topic discovery. Each path offers source intake when needed and
uses a saved voice, a newly learned voice, requested tone, or existing-draft voice.
The parent loads stage modules progressively and preserves the requested stop point.

Profiles distinguish author background, observed style, and explicit rules.
Input items have purposes: manuscript, outline, factual reference, inspiration,
voice sample, and author background. LinkedIn URLs, pasted content, exported
archives, authored blog links, and uploaded samples are accepted through host
capabilities; unavailable content is recorded, never silently treated as read.

Portable local state stores author profiles, reusable sources, article briefs,
interview answers, outlines, manuscript versions, review records, and next steps.
Article state pins a profile revision and selected sources. Source or manuscript
changes invalidate affected checks. Imported manuscripts remain preserved.

## Acceptance criteria

- Generic requests receive useful starting choices; explicit requests bypass them.
- Intake offers uploads, pasted text, links, existing material, or no material.
- Voice setup works independently, produces an audition, and saves revisions.
- Outline-only stops at an outline; express does not require outline approval.
- Interviews ask one question at a time and reuse known answers.
- Article and profile progress can be reopened without redoing intake.
- Source records retain purpose and provenance; facts and style are not conflated.
- Revision is recoverable and stale, failed, and unavailable reviews are distinct.
- Local helpers pass disposable end-to-end tests; the relocated archive validates.

## Boundaries

No BlogForge UI/server changes, live publishing, paid provider calls, hidden
credentials, automatic account access, or automatic global installation. The
package is usable by local path now and installable as a complete skill folder.
Host attachment tools supply uploads; skills cannot create a new file picker.
Profile creation and auditions are model-guided; helpers store/check artifacts,
not a substitute writing model. GEO is editorial readiness and humanization is
style review, with no guaranteed citation or authorship verdict.
