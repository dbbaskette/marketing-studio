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

## Completion evidence

Application tree `2e80969d` was verified in disposable Tart macOS 27 guests with
Python 3.13.15 and Node 22.23.2. Every test VM was stopped and deleted.

- The full shared run exercised 1,070 tests with one PDF-tool environment skip.
  Its only failure expected the old unconditional "research is reviewed" handoff
  sentence. The updated test checks warning preservation, excluded-claim handling
  and honest verification language. All 98 affected shared research/handoff tests
  then passed on the final application tree, including the subsequent timeout and
  older-run recovery cases.
- All 3,196 Training Studio tests and package validation passed. This includes
  creator decisions continuing into material authoring, no-job saves, stale and
  active-run refusal, exclusions, missing verdicts, and unchanged spending allowance.
- All three affected Presentation Studio parallel-research tests passed.
- The native browser journey passed at phone and desktop widths in light/dark
  modes with reduced motion: initial focus, no default inclusion, required choices,
  source links, include/exclude save, no horizontal overflow, and zero extra jobs.
  The primary implementer visually inspected the phone form. Frontend code was
  unchanged by the subsequent recovery refinements.
- A saved failed run can use the creator path without being deleted or restarted
  from scratch. The actual user's workspace and active run were not modified;
  no live provider acceptance test or automatic software restart was performed.
