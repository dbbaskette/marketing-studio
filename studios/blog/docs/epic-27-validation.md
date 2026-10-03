# Epic 27 implementation and validation

Runtime 1.7.0 implements the five author-workflow slices in epic #27. This record
describes implementation verification before integration. Installing the updated
runtime in an existing author session is a separate step.

| Issue | Delivered behavior | Main verification |
| --- | --- | --- |
| #30 | Short-command plans with selected-article resolution, destination clarification, ordered pull/proofread, and focused skill routes | Alias, ambiguity, missing article, and compound-route fixtures; plans never claim execution |
| #31 | Chat status card, active selection, title lookup, Google/GitHub links, separate local/Hub state, historical timestamps, optional technical details | Local, external-edit, queue, pending-review, shared, conflict, unavailable, and live-read-result fixtures; direct Markdown rendering |
| #32 | Local personal defaults and portable team context defaults; request/article/personal/team precedence; profile pin projection across members | Precedence, reset/tombstone, missing profile, imported-voice preservation, conflict, cross-member voice, and private-value exclusion fixtures |
| #33 | Local history and cached Hub comparisons; supplied Google readback compared against the transfer baseline; bounded section excerpts and formatting evidence | Changed sections, both-sides-changed, missing formatting baseline, formatting-only snapshot history, and local-versus-Hub fixtures |
| #34 | Read-only restore preview and guarded apply; new text revision with current dependency pins; stale reviews; ordinary Hub publication | Stale preview refusal, history preservation, path validation, no Google write, no preview publication, and exactly one apply publication |

## Test boundary

`tests/test_author_workflow.py` contains 13 deterministic tests. These use temporary
workspaces and local Git repositories with the existing fake GitHub boundary; they
make no model calls or live Google writes. Existing tests cover the underlying
Google transport/checkpoint protections and Hub conflict lifecycle.

The initial host suite passed 162 tests (153 existing plus the first 9 new tests).
The final Tart suite passed **166 tests in 111.529 seconds** on macOS 27.0
(26A428), Python 3.13.15. The guest’s complete CI script returned PASS, including
Codex-only, Claude-only, and both-target offline install/check/uninstall checks. The
four added edge-case tests also passed locally. Required package validation,
character-based guidance inventory, checksums, skill validation, newcomer prompt
checks, and launcher syntax checks are included in verification.

## Compatibility and use

Update through the trusted 1.7.0 installer and start a new session for the new
helpers and bootstrap instructions. Existing writing guidance pins remain selected.
New task guidance requires runtime 1.7.0; older installers remain supported for
older packages. New personal selection/default files are workspace-local and are
excluded from Hub payloads. Team default records use existing scoped context and
voice dependencies; this change does not migrate the Hub format.

The status card is Markdown in the harness: say **Show status**, or **Continue
[title]**. The direct helper is `studio.py --root <workspace> status --format
markdown`; `--online` checks a linked Google Doc. The card labels Hub observations
as last known; refresh the selected Hub for an up-to-date remote comparison.
See [status-card usage](status-card.md).

Restore is a draft/outline text operation. It deliberately retains current source,
voice, rules, and writing-guidance pins. It does not reconstruct a historical
Google layout, reset Git history, or overwrite Google. Formatting comparisons use
captured evidence; a native fingerprint change combined with changed text alone
is not labeled a proven formatting edit.

## Remaining live acceptance

Keep actual Codex/Claude conversational behavior, cross-member remote behavior,
and real Google fidelity checks in existing issues #9, #10, and #15, run last.
Passing deterministic routing tests is not evidence that a live model completed
a Google transfer. This implementation performed no live document mutation,
article publication, user-runtime update, or account change.

## Final evidence

- Local logs: `/private/tmp/blog-studio-epic27-tests.log`.
- Final guest logs and installation results: `/private/tmp/blog-studio-epic27-ci-results/`.
- `runtime_integrity` was `verified` for the both-target installation.
- User-guide links and both distribution checksums validated.
- A synthetic status card was rendered from the real helper in
  `/private/tmp/blog-studio-epic27-demo/status-card.md`.
- The separate disposable CI clone was removed after success. The signed-in author
  VM and its installed skills were not changed.
- Tested runtime manifest SHA-256: `6c5cc61e6df948fd1495d4d0763cf353c96e8458bc0af07ec29c8131c3ede1c3`.
