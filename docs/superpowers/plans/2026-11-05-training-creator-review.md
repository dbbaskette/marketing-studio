# Training Studio: creator decisions on research flags

Issue #385. Authorized by the request to stop repeated verification loops and let
the creator choose whether flagged source material belongs in the training.

## Design

Training Studio performs one independent check per explicit attempt. A structurally
valid draft with unresolved semantic objections or unread originals becomes a
creator decision, retaining the exact draft, citations and independent verdicts.
Each flag requires Include with warning or Exclude; there is no default acceptance.
An explicit retry may correct the affected work and run one further check.

Creator approval is a separate Training Studio handoff, never a forged successful
Harness Research review. Its deterministic report excludes rejected claims and
dependent prose, labels included uncertain material, preserves the original review,
and binds decisions to the exact draft and research inputs. Source integrity,
permissions and malformed artifacts remain hard checks. Material authors receive
the decision-qualified report. Existing downstream review gates still apply.

Preserve final-author objections when another section is rewritten, including
introduction, brief and comparison feedback. Do not modify an active user run.

## State transitions

| Before | Event | After | Verification |
| --- | --- | --- | --- |
| Research working | Check accepts all content | Existing reviewed research handoff | Native regression |
| Research working | Valid check leaves flags | Await creator; no automatic correction loop | Real-helper test |
| Await creator | Include/exclude every flag | Creator-approved report, waiting for Continue | Native/UI journey |
| Await creator | Retry explicitly | Affected correction plus one check | Real-helper recovery |
| Creator form open | Draft, inputs or owner changes; job starts | Refuse stale/active decision without mutation | Native conflicts |
| Flagged claim | Exclude | Claim and dependent content omitted | Dependency tests |
| Flagged claim | Include | Warning and original verdict retained | Bundle/UI tests |
| Section corrected | Final author runs | Outstanding final feedback retained | Correction regression |

## Verification

Use disposable fixtures and the pinned real helper with scripted workers. Cover
integrity, exact revision binding, source flags, dependent exclusions, no-job
decision saves, subsequent authoring, and phone/desktop keyboard interaction.
Run the relevant shared and Training Studio suites once in disposable local CI.
Synthetic results do not establish live provider latency or semantic accuracy.
