# Training Studio single topics review: implementation plan

Approved correction: Training Studio does most work. Show planned topics, offer
changes, then build. No sample lesson or separate learning-brief interview.

## 1. Versioned native review

Add `runner/training_plan.py` to read existing checked blueprints and insert one
review after every level's plan is ready, before material writing. Save a schema-6
run marker, exact content basis and review revision. New default runs use this
review; old schemas retain their flow. Reuse existing plan revision requests and
native continuation. Do not add another author job or repeat research.

The existing blueprint parser remains the content authority. The new overview
only extracts readable topics, objectives, examples, practice and gaps. Confine
file reads to the training folder. Preserve source and budget guards.

## 2. One simple desk decision

Expose the native decision through an authenticated page endpoint. Add one topics
review to the existing Training Studio desk with **Ask for changes** and **Build
the training**. Preserve typed notes/focus; hide premature delivery controls and
empty material cards while preparing/reviewing the topics. Reuse existing styles.

Build continues all selected materials, including drafting/designing the deck,
without another default content approval. Keep final Ready/delivery explicit.
Presentation Studio and older saved Training Studio runs are unchanged.

## 3. Content direction and documentation

Keep the current short start form. Clarify that the topic can describe the learner's
task, depth and desired examples. Make level guidance defer to the person's stated
task/audience and accepted plan. Update user docs and this transition matrix.
No new dependencies, frontend build or research implementation.

## State-transition matrix

| Trigger | Expected result | Verification |
| --- | --- | --- |
| New run | Research and plan automatically; stop before materials | Native journey |
| All levels' plans ready | One combined topics review | Multi-level journey |
| Ask for changes | Revise plans, keep research, return to review | Native + page journey |
| Missing note / changed version | Refuse before dispatch | Native + private API |
| Repeated old decision | Refuse; no duplicate work even with identical plan text | Revision regression |
| Build current plan | Generate all selected materials without sample/extra content stop | Native + browser |
| Active job / paused work / foreign owner | Preserve current work; refuse premature decision | Guard regressions |
| Outside/symlink plan path | Refuse read and approval | File-confinement regression |
| Old schema / restart | Retain original workflow; unsupported schema-6 marker refuses | Compatibility |
| Completed material | Draft until person marks Ready; external delivery remains explicit | Native + existing suite |

## Verification ownership

One implementer owns targeted native/API and actual-page script checks, followed
by the complete Training Studio suite through the existing shared Tart runner.
Exercise the real native page and engine with synthetic authors in Playwright at
phone and desktop widths, including a change request and Build. Run package,
standalone setup/launch and existing disposable CLI/Hub acceptance gates. Check
relevant root UI/packaging contracts; reuse valid unchanged other-studio evidence.

Use disposable settings, source fixtures, workspaces, identities and processes.
No real provider jobs, Google writes, user-training resets or automatic migration.
Publication and restart remain separate actions.

## Completion record

Complete. The native single/multi-level, changes, duplicate/version, restart,
authentication and parallel-research journeys pass. Actual desk-script checks cover
one primary action, note preservation and exact decision payloads. Real native-page
browser journeys pass at phone and desktop widths, including requesting changes,
approving the revised plan and completing the materials. The page waits for the
revised plan to finish refreshing before the browser takes its next action.

The complete Training Studio suite passes (3,006 tests), as do package validation,
19 relevant shared-UI/core checks, all four independent setup/launch journeys and
the existing 41-step Blog Studio Hub and 39-command shared-studio CLI journeys.
Verification uses synthetic authors and disposable macOS settings/workspaces.
No live provider or Google delivery was tested. Existing user runs were untouched;
publication and activation in the running app were not part of this change.
