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

## Commands and outcomes

- `python -m unittest discover -s tests -p 'test_blog_runner.py'`: 23 targeted
  checks passed, including an authenticated HTTP run through all four writing
  gates, real subprocess adapter fixtures, cancellation, manual-edit protection
  and a second-clone Hub handoff with selected sources and voice.
- `node scripts/ci/check-management.cjs`: passed, including page decision tokens,
  chat/page controls, retry rendering and element IDs for both browser scripts.
- `python scripts/acceptance/hub-journey.py --local-fixture --run-directory
  /tmp/blog-studio-runner-hub-acceptance-20261014`: PASS, all 41 real CLI steps.
  Covers create/join, source and voice intake, blog saves, reviews, cross-clone
  resume/edit, offline queue/retry, status, readable folders and overwrite guards.
- `python skills/blog-studio/scripts/validate_package.py` and
  `python scripts/build.py --check`: passed; package links and reproducibility
  were checked. Guidance remains within the recorded budgets.
- Desktop layout inspected in the collaborative browser using the actual page,
  CSS and scripts with synthetic API responses. The new-blog form and review
  dialog were inspected. A form-padding problem was corrected. The browser
  could not reach the local server, so this is layout evidence, not a browser
  to server acceptance run. The HTTP pipeline was exercised separately.

The full local suite and Tart results are recorded with the pull request.
Live model calls, multi-account GitHub permissions and live Google transfers
were not exercised. Two local clones of one fixture account establish neither
multi-account permissions nor Google acceptance. This runner uses the existing
CLI source boundary, not Training Studio's research companion: its browser
research reports and citations still need human review.
