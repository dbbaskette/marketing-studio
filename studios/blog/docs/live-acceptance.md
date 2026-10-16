# Live acceptance: Codex, Claude, Google Docs, and Team Hub

Run local automated tests in Tart first. Live CLI checks use the user's existing
CLI sign-ins and a separate disposable writing directory with fictional material.
Never reuse the current writing session, copy credentials, or upload real drafts.
The live runner does not belong in unattended CI: it makes real model requests.

## Writing acceptance

Run `python3 scripts/ci/live-writing.py --harness codex --output <new-directory>`
or replace `codex` with `claude`. Keep the output outside the skills repo. It uses
a project-local copy of the current full skill, so it evaluates candidate guidance
without updating the user's installed skill or fetching main. Each request starts
a new CLI process and resumes work from disk. Logs stay local; publish only a
redacted observation report. The script records artifacts and objective checks;
a person must inspect responses for source fidelity, one-question interviews,
voice quality, and whether stated limitations are accurate. A process exit alone
is not a passing writing test.

The scripted requests cover outline stops, draft adoption, saved-article search,
active memory correction/forgetting, resume, and original-preserving revision.
Use the new-user guide for standalone voice, discovery, from-outline, and interview
acceptance. Repeat only cases affected by a fix. Installed bootstrap discovery,
online refresh, offline fallback, and managed runtime updates are separate checks.

## Google round trip (selected test destination required)

1. Select a disposable Google folder/document and its intended audience. Inspect
   connected tools in each actual harness. Record observed read/create/edit/copy/
   export/comment/revision/tab capabilities individually; a synced Workspace skill
   does not prove authorization or tool availability.
2. Read fictional source notes; draft locally; post only the chosen draft. Inspect
   inherited audience before placing it in a folder and verify the written body.
3. Make one authorized document edit and one local edit, then bring edits back.
   Verify original/history/pins and either clean merge or explicit conflict. Retry
   the same transfer to check idempotency. Stale affected review results.
4. Test supported review/template/export actions individually; inspect returned
   permissions and rendered exports. Record unsupported operations as unavailable.
   No sharing changes, invites, notifications, or real private sources are implied.

## Two-person Team Hub (second member required)

Use a selected private disposable hub and two already authorized members with
separate clones. Confirm member B can find/read A's article and exact pins. Both
edit the same baseline; synchronize and verify explicit conflict resolution keeps
both histories. Test a queued offline save and a shared rule correction/retirement.
Verify active article pins do not silently adopt changed defaults. Report protected
branch/read-only behavior if those permissions are actually available; do not
simulate two real users by claiming two local fixture registries are live evidence.

Keep evidence in `docs/usability-validation.md`: date, candidate tree fingerprint,
CLI/runtime versions, fixture-versus-live distinction, actual outcome, and remaining
requirements. Never include tokens, email addresses, private article excerpts, or
unselected document contents. Existing live issues #8–#10 and #15 stay open until
their actual acceptance criteria are observed.
