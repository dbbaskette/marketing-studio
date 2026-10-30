# Training Studio: recognizable form selections

The Yoodli option looks like a command button. Replace independent start-form
choices with native checkboxes using the existing shared checkbox component and
opaque Golden Gate-inspired form surfaces. Levels, materials, Yoodli, optional
design review and document copies use visible checked state; exclusive choices
keep their segmented controls. No new theme, framework, backend state or provider
operation is introduced.

| Interaction | Expected state | Verification |
| --- | --- | --- |
| Focus Yoodli | Focused but still unchecked | Native browser |
| Space / click its label | Checked; required materials included | Browser + screen suite |
| Remove a required material | Yoodli unchecked; inline explanation | Browser + screen suite |
| Uncheck Yoodli | Other selected materials remain | Browser + screen suite |
| Choose levels/copies/design review | Correct native form payload retained | Complete frontend suite |
| Invalid empty form | Focus the actual missing checkbox | Screen regression |

Verify the complete Training Studio browser-script suite, package and shared UI
contracts, plus actual phone/desktop light/dark pages with keyboard and touch-target
checks. Reuse valid native backend suite evidence: no backend or content contract
changes. All fixtures remain disposable and synthetic, with no provider jobs.

The running application's checkout has unrelated local design edits. Preserve it;
activation requires selecting the fixed checkout explicitly. Do not overwrite its
files or restart an active application as part of visual verification.

Complete locally. The 228 browser-script checks pass, followed by 41 layout checks
and three migration-page checks. Shared UI/layout/gateway checks pass (29), and
package validation passes. Actual 390/1280-width native pages verify keyboard
Space selection, focused-but-unchecked state, dependency preservation, 44px phone
label targets, no horizontal overflow, light/dark appearance and PDF intake.
Current backend and other-studio full-suite evidence is retained unchanged.

The additional other-studio review is recorded in
[`form-choice-audit.md`](../../design/form-choice-audit.md). Findings outside
Training Studio are recommendations; those pipelines have not been modified.
