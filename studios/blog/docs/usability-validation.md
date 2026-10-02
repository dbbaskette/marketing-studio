# Short-term usability validation — October 2, 2026

Candidate runtime: **1.3.0**, based on main
`e6b853a145bb781253020524b07362d893a2c4d3`. Changes remain local pending publication.

## Implemented

- Read-only readiness: Python/Git, installed runtime hashes, actual CLI sign-in,
  optional approved-main access and runtime release metadata, recovery steps.
  Google remains explicitly unverified until a selected-document read succeeds.
- Start or continue: existing six writing modes plus saved work; optional sources
  and voice; clear requests skip menus; setup/help never creates an article.
- My blogs: bounded metadata search, stage/last activity/next step, pagination,
  duplicate-title disambiguation and existing exact-pin resume.
- Visible article context and revisioned remember/correct/forget controls;
  article-only detachment of a shared rule; scoped author/team guidance continues
  through existing profiles and hub revisions/tombstones. History remains intact.
- Reusable opt-in live CLI runner and explicit Google/two-person acceptance protocol.
  New-user guide included in the installer bundle; both archives rebuilt.

## Automated evidence

In the existing Tart VM, using **Python 3.13.16**: **119 tests passed in 56.507s**.
The suite covers article helpers, installer integrity/rollback, extracted
bundle execution, guidance pins, Google checkpoints, shared-workspace concurrency,
and the new discovery/memory/update-metadata tests. The same 119 also passed under
macOS system Python 3.9.6 during diagnosis, but 3.11+ remains the supported contract.

After the final readiness guard for malformed/incomplete manifests, all seven
readiness/discovery/memory tests and the extracted-bundle test passed again.
Additional checks: both package validators, skill frontmatter validator, newcomer
prompt-generator checks, shell syntax, guidance inventory, patch whitespace, and
full offline ZIP contents/checksum. A disposable managed installation for both
harnesses verified runtime integrity and was uninstalled without changing the
user's active installation. Readiness made no writing workspace and returned no
account email, organization ID, or authentication output.

The first readiness run correctly detected macOS system Python 3.9.6 instead of
Homebrew Python 3.13.16. The bootstrap now tells the harness to use the interpreter
recorded by the installer for every helper command. A supported-interpreter check
reported both CLI sign-ins and access to approved main. The 1.3.0 candidate correctly
reported that approved main still shipped 1.2.0; no update was installed globally.

Usability milestone operational-skill tree SHA-256:
`592a6e360562f527752bd604b45b322fd0b18cf966a3422e3539b95524552f11`.
Usability milestone bootstrap tree SHA-256:
`8b489a26db93e0ce03cedbbb678a59de4ad9424640ccee4ac1730fdd33feb66b`.
These hash sorted relative filenames, a NUL byte, and file bytes; omit Python caches.

## Actual CLI evidence in Tart

Codex **0.160.0** and Claude Code **2.1.285**, with the user's existing sign-ins,
ran in separate disposable directories using fictional notes. No browser writing,
real private articles, external research, Google documents, or team uploads.
Each request used a new CLI process and recovered writing from saved files.

| Observation | Codex | Claude Code |
| --- | --- | --- |
| Save outline and stop without draft | Passed | Passed |
| Resume by title; adopt requested draft stop; save draft | Passed | Passed |
| Save short-heading preference; correct it to descriptive headings | Passed | Passed |
| Forget preference; preserve draft bytes | Passed | Passed on focused retry |
| Revise separate manuscript; retain byte-identical original | Passed | Passed on focused retry |

The initial Claude invocation hit a runner argument-parsing error. After that fix,
two later turns tried relative/global helper paths outside the runner's explicit
allowlist and remained incomplete. Focused retries named the selected offline
runtime and completed with zero permission denials. The runner now specifies its
offline runtime/interpreter, preserves failed attempts, and checks artifact outcomes
rather than treating exit code zero as acceptance. No permission bypass was used.

Claude's first outline response also admitted it had not reopened the saved file.
The helper now reopens each saved article artifact and compares its bytes before
returning `saved_artifact.reopened`. This deterministic correction and interpreter
routing were added after the live writing runs and verified by the final automated
suite; a new complete live matrix of the final tree is not claimed.

Core writing source fidelity and memory responses were inspected. Codex's first
outline response contained an inaccurate lowercase file link although the actual
saved artifact was `OUTLINE.md`; broader user-facing output/link polish remains in
M5. No six-route/voice/interview or installed-bootstrap live completeness claim is
made by this five-request candidate-package test.

## Remaining real-service acceptance

The fifth recommendation is **partially validated**, not complete:

- Google source → draft → review → return still needs a selected test document/
  folder and audience. Tool names are available in this host, but that does not
  establish a usable connection in either guest CLI. No real Google read/write
  was attempted; local Google fixture tests are separate evidence.
- A two-person private Team Hub pilot needs the chosen repo and a second authorized
  member. Two local fixture registries test synchronization, not real membership.
- Remaining I4/M5 scenarios include authentic browser-download quarantine, full
  installed-skill discovery/refresh/fallback, all six starts, voice/interview,
  and real file/link extraction behavior. Existing live issues stay open.

Follow [the live acceptance protocol](live-acceptance.md) and
[the new-user guide](new-user-guide.md). Raw transcripts remain in the disposable
VM under `/private/tmp/blog-studio-usability-20261002/`; they are not committed.

The later author/title library is covered by [its own validation record](team-hub-library-validation.md).
