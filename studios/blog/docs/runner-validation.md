# Guided blog validation

All automated and walkthrough content is synthetic. No provider credentials or
real team writing belong in fixtures. The browser smoke run uses a scripted
worker, not a live assistant.

## State transitions

| Trigger | Before | After | Coverage |
| --- | --- | --- | --- |
| Create in chat | No run | First stage pending, conversation decisions | CLI flow |
| Create on page | No run | First stage queued on this computer | Idempotent creation |
| Worker submits | Current stage pending | Current draft awaiting approval | Worker gate |
| Submit later stage | Earlier stage not approved | Refused | Conversation gates |
| Approve current version | Current draft | Next stage pending or complete | Conversation gates |
| Approve from CLI | Page decisions | Refused | Approval boundary |
| Page decides chat run | Conversation decisions | Refused until explicit takeover | Handoff |
| Request earlier revision | Approved or current stage | Revision pending, downstream decisions removed | Invalidation |
| Edit saved file | Current draft/approved | Stale, cannot approve | Manual edit |
| Scheduler sees manual edit | Locally enabled | Paused for review; no automatic overwrite | Background edit protection |
| Review saved version | Stale stage | Same text returned for approval | Saved-version adoption |
| Old decision token | Run changed | Refused | Version-bound decisions |
| Late worker after local edit | Worker active | Edit retained, returned draft refused | Concurrent edit |
| Stop | Working | Child stopped, no late save | Cancellation |
| Pause | Working | Current stage retained, no new work | Pause check |
| Reopen page process | Locally enabled run | Resume from saved state | Restart |
| Checkout from another clone | Shared run | Decisions retained, execution paused | Hub round-trip |
| Continue in chat | Page decisions | Worker stopped, conversation decisions | Handoff |
| Run this from here | Conversation decisions | Page decisions, queued locally | Handoff |
| Import existing manuscript | Saved draft | Review pending, manuscript unchanged | Existing draft |
| Read-only Hub write | Any page mutation | Refused | Access boundary |
| Choose a mode | New blog | Write/outline/revise/review pipeline, original retained | Mode matrix |
| Change page defaults | Existing runs | Future page defaults saved locally; runs unchanged | Local settings |
| Compare a revision | Earlier approval exists | Exact approved snapshot and current diff | Document and Hub round-trip |
| Server changes while reading | Review page open | Existing document retained, approval disabled | Browser and DOM |

## Commands and outcomes

Use the checkout’s Python 3.11+ interpreter (`.venv/bin/python` locally).
All reports below were produced on 2026-10-14.

- `BLOG_STUDIO_TEST_JOBS=8 bash scripts/ci/check.sh "$PWD/.venv/bin/python"
  /tmp/blog-studio-training-parity-check-20261014`: results are recorded in that
  directory and on the pull request.
- `python -m unittest discover -s tests -p 'test_blog_runner.py'`: 28 targeted
  checks passed, covering authenticated HTTP gates, both subprocess adapters,
  cancellation, edit protection, modes, local defaults, approved comparisons and
  a second-clone Hub handoff with selected sources, voice and approval history.
  The final completed-page revision regression also passed separately with
  `-k completed_page_revision`.
- `node scripts/ci/check-management.cjs`: passed after the final page edits.
  Covers explicit confirmation, version tokens, rendered Markdown, unsafe link
  refusal, stale-reader protection, navigation during creation, wizard modes,
  completed-run revisions, handoff controls and the existing editorial tools.
  The DOM fixture now respects the browser’s read-only textarea `type` property.
- `python scripts/acceptance/hub-journey.py --local-fixture --run-directory
  /tmp/blog-studio-training-parity-hub-20261014`: PASS, all 41 steps.
  It records the real commands for create/join, source and voice intake, blog
  saves, reviews, cross-clone resume/edit, offline queue/retry, status, readable
  folders and overwrite guards. The preceding 41-step walkthrough also passed.
- The real CLI mode walkthrough passed all 24 commands. It creates write,
  outline, revise and review runs, submits and approves each planned stage, and reopens the retained originals.
  Report: `/tmp/blog-studio-training-parity-modes-report.json`.
- `python skills/blog-studio/scripts/validate_package.py`, the skill-creator
  `quick_validate.py` (with PyYAML supplied by uv), and guidance budgets passed.
  The copied Training Studio stylesheet and Markdown renderer match both the
  recorded hashes and the inspected source revision; its MIT license is bundled.

The collaborative browser reached the actual authenticated loopback server
using the real HTML, CSS, scripts and HTTP routes, with a scripted worker. It
saved settings, created and completed an outline through all three wizard steps,
approved writing stages, requested an earlier draft revision, opened the exact
last-approved comparison, and verified an outside edit preserves the document
being read while disabling approval. Desktop and 390-pixel mobile layouts were
inspected; mobile has four tabs and no horizontal overflow. Escape closes the
comparison sheet and restores background interaction. Report:
`/tmp/blog-studio-training-parity-browser-report.json`.

The initial Tart matrix passed Linux 3.11 and 3.13. Both macOS jobs failed before
tests because the runner environment could not obtain the pinned Ruff 0.15.14.
The final commit uses the existing Tart workflow again; current job results are
recorded with the pull request. No workflow files were changed.

Live model calls, multi-account GitHub permissions and live Google transfers
were not exercised. Two local clones of one fixture account establish neither
multi-account permissions nor Google acceptance. This runner uses the existing
CLI source boundary, rather than Training Studio’s research companion; public
research reports and citations still need human review.
