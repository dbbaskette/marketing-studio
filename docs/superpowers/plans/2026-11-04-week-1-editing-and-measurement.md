# Week 1: editing reliability and measurement

Authorized scope: #312, #313, #314 and #319; companion feasibility for later cohorts.

## Implementation

- Preserve retained editor nodes while replacing status panels. Hold composition input until it completes and retain selection when an editor must be replaced.
- Give the Library picker one scrolling content area and a separate confirmation footer.
- Return successful pasted-source capture to the persistent Paste text action.
- Keep allowlisted operation milestones in the existing private Activity log. Report known queue, assistant, checking and ready-for-person intervals, first saved output and saved-unit count. Saved output is provisional; unknown boundaries remain unknown.
- Record actual pinned Harness Research and Harness Slides contracts in `docs/research-responsiveness-contracts.md`. Do not change companions or installed skills.

## Verification

- Native Presentation Studio keyboard journey: complete character-by-character input across the dirty transition, then autosave; focus and mid-text caret retained.
- Regression tests model focus loss on DOM detachment, successful source focus, first result during parallel work, same-second idempotence, milestone retention and separate check/wait boundaries.
- Library browser journey checks confirmation visibility at 320, 390 and 1280 pixels, at both ends of the list.
- Full shared/native/package/CLI acceptance uses the existing disposable Tart runner. No live model, signed-in provider, real workspace or Google write is used.

## Review boundaries

Timing is recorded activity, not a provider-speed benchmark or ETA. Journals are bounded; historical jobs predating instrumentation may have no usable timing. The journal cannot make a successful content save fail.

Week 3 can use the pinned research area protocol. Section-level independent review reuse remains later companion work; the current independent review covers the complete dossier.
