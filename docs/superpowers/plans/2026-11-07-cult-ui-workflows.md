# Cult-inspired Training Studio workflows

The approved design adapts Cult UI interaction patterns to the existing JavaScript,
CSS and Golden Gate 2.1 system. No framework, build step, provider work or authentication
change is needed. Preview/content surfaces remain opaque; accent, borders and brief
state transitions provide emphasis. Reduced motion keeps every action immediate.

## Delivery order

1. **#429 — slide inspector.** Keep preview and focused text/review tools together on
   wide screens. On narrow screens show one task with a clear return to Preview.
   Keep History accessible, the selector mounted, and unsaved edits and selected
   fixes stable. Own files: Training Studio `desk/drafts.js`, shared stylesheet,
   affected page tests and browser fixture. Verify keyboard, phone/desktop geometry,
   scroll, pending text and navigation that starts no work. Push and merge this slice.
2. **#430 — progress and feedback.** Compact current-stage summary, actual draft
   counts and direct draft access, expanding into the existing detailed workflow.
   Keep stop/retry/approval controls and unknown duration honest. Dismissible action
   notifications distinguish queued work from completion. Own the Training Studio
   progress/toast functions, CSS and their regressions. Push and merge this slice.
3. **#431 — guided forms and delivery.** Navigable form steps with clear current and
   completed states, concise summaries, existing validation and retained input.
   Group delivery commands into an expandable workspace control. Preserve explicit
   Start, Save and Send decisions and nested-source focus return. Push and merge.

## Verification ownership

The implementing agent owns affected module suites and a disposable browser journey
for each slice. One final full Training Studio run through the shared Tart runner
owns integrated verification; reuse preceding evidence for unchanged code. Shared
style/intake checks cover any shared changes. All fixtures use synthetic content and
fake providers. Keep the running user app and workspaces untouched.

## Review focus

Navigation must never start work, close unsaved edits or reset scroll. Desktop preview
must remain useful alongside the inspector; phone controls must fit and remain reachable.
Progress must distinguish availability from approval, and toasts must never report queued
work as complete. Do not hide required validation or bypass existing revision guards.

## Completion

- #429: merged in [PR #432](https://github.com/dbbaskette/marketing-studio/pull/432); 146 affected UI/layout cases and 14 shared style checks pass.
  Desktop/phone walkthrough retains pending text and review choices without overflow.
- #430: merged in [PR #433](https://github.com/dbbaskette/marketing-studio/pull/433); compact draft access, expandable workflow and dismissible action feedback.
- #431: implemented; guided creation steps, concise settings context and grouped export controls. Integrated verification pending.
