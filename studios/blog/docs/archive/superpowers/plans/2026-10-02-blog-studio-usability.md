# Blog Studio short-term usability release

Approved: user requested implementation of all five recommendations on 2026-10-02.

1. Read-only readiness: runtime integrity, CLI sign-in, optional approved-main
   availability, and honest Google capability guidance. No automatic account changes.
2. First-run start/continue route: retain six existing writing modes, optional sources
   and voice, skip menus for clear requests, never initialize an article for help.
3. Bounded article discovery by title/ID, newest first, stage/next step, resume exact pins.
4. Inspect selected context; revisioned article preferences; correct/forget/detach;
   use existing revisioned author profiles and team tombstones for those scopes.
5. Reproducible live CLI acceptance and Google/two-person pilot protocol. Run isolated
   checks without touching the user's active CLI session. External pilot requires a
   selected Google destination and a second authorized participant/hub.

Validation: targeted runtime invariants, then the complete suite and distribution
checks on the final source tree using Tart. Record real CLI observations separately
from fixture evidence. Preserve the existing new-user-guide work. No publication
requested for this change yet.

## Completion record

Items 1–4 are implemented. Item 5 has a working opt-in CLI runner, five core
writing observations in both CLIs, 119 automated tests in Tart, and a concrete
external pilot protocol. Google and two-person live acceptance remain pending
selected destinations/participants; see [evidence](../../usability-validation.md).
