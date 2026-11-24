# G0–G3 validation record

Implemented on `codex/google-docs-workflow`, based on main `52977c4`.
Runtime 1.2.0 adds local checkpoint commands and six conditionally loaded Google
capabilities. Google operations still execute through the user's connected
harness; fixture checks cannot establish live provider behavior.

## Completed checks (2026-10-02)

- Full local suite: **111 tests passed**, 64.072 seconds.
- Fresh Tart clone: **111 tests passed**, 56.003 seconds, macOS 27.0 (26A428),
  Python 3.13.16. The existing stopped disposable Python-equipped VM was cloned;
  the shared Golden Gate base and user accounts were not changed.
- Tart guest completed install/check/uninstall for Codex, Claude and both,
  GUI-path launcher discovery, newcomer prompt checks, both package validators,
  and the guidance inventory check. Its final result was `PASS`.
- Skill frontmatter validation and offline/installer archive integrity passed.
  Final documentation corrections were followed by archive rebuilds and the
  extracted-bundle test; executable code was unchanged from the full-suite run.

Local logs: `/private/tmp/blog-studio-g0-g3-tests.log`.
Tart results: `/private/tmp/blog-studio-g0-g3-tart/blog-studio-test-20261002040102-41629/`.
The runner stopped and retained that disposable clone.

## New coverage

The new transfer tests cover the round trip; original/history and voice/guidance
pins; stale editorial reviews; outline-only preservation; both-sides-changed
conflicts; explicit merges remaining unsent; local edits made during a handoff;
changed comparison inputs; pending/duplicate/out-of-order confirmations; changed
Doc IDs/tabs/folders; missing revision guards; failed readback; malformed or
secret-bearing metadata; no-network execution; and Team Hub checkout/republication
on another member's workspace.

Receipt tests cover exact requested recipients, partial permission results,
public/extra grants, native-anchor/thread readback, template structure assertions,
and export version/inspection consistency. They validate bounded assertions from
the harness, not the truth of provider actions. The installer rejects a 1.2.0
bundle missing its new managed helper; the extracted runtime exposes its commands
from either supported harness installation path.

## Deferred live evidence

No Google account was read or changed. No sign-in, model call, sharing action,
comment, live export, or paid-service operation was used for this implementation.
The Codex capability inventory is based on exposed tool schemas and current
provider skill guidance. Claude parity, accepted-text rendering, native inline
anchors, complete template fidelity, real output inspection and actual
permission/notification behavior remain unverified.

Run authenticated pilots last: [I4 #8](https://github.com/dbbaskette/blog-studio/issues/8),
[M5 #9](https://github.com/dbbaskette/blog-studio/issues/9),
[H4 #10](https://github.com/dbbaskette/blog-studio/issues/10), and
[G4 #15](https://github.com/dbbaskette/blog-studio/issues/15).
The Google pilot must use explicitly authorized disposable documents/folders in
each intended harness. An API-created quote is not proof of an inline anchor;
a receipt is not publication approval or evidence of an external call.
