# Form-choice audit

Scope: the four studios and shared Marketing Studio settings. Review source
behavior and control semantics, with actual disposable browser verification for
the Training Studio correction. No personal projects, settings or running apps
are changed by this review. This is Golden Gate-inspired web UI, not native
macOS system material.

## Findings

| Area | Finding and effect | Recommended control | Status |
| --- | --- | --- | --- |
| Training Studio new form | Levels/materials, Yoodli, optional slide-design review and copies were pill buttons, making focus look like a selection and commands look like settings. | Native checkboxes, explicit checked state, nearby dependency feedback; retain exclusive deck/delivery segments. | Implemented and browser-verified in the current change. |
| Presentation Studio new form | `settingsStep` uses a chip for **Research first**. The choice rerenders the form but does not itself research; a command-looking control obscures its state. | Native checkbox with its existing explanation and preserved focus. | P2 follow-up. |
| Presentation Studio research review | **Bring the evidence up to date** is a chip setting used only when the later change request is submitted. Its action-like label can suggest research starts immediately. | Native checkbox with cost explanation next to it. | P2 follow-up. |
| Presentation Studio slide review | **Ask for changes to this slide** and **Change what it says** are marks for a later request. Selecting either clears the other; neither immediately submits the change. | An explicit **No change / Edit text / Redesign** exclusive choice per slide, with the relevant note and a separate submit action. | P2 follow-up. |
| Presentation Studio document review | **That’s wrong** is a chip that changes the pending classification used by Approve. | Explicit correction choice naming the resulting document/deck type. | P2 follow-up. |
| Presentation Studio start guidance | `startsSays` promises **no stops** (or only a look-choice stop), while new runs require slide-text approval before design. | Explain the text-approval checkpoint, then optional look selection. | P2 follow-up. |
| Infographic Studio story selection | Every story has a filled **Use this story** button; the current story becomes another clickable **Selected** button without a programmatic selected-choice state. Multiple peers compete as primary actions. | Clearly marked single-choice story cards/radios and a separate Build action. Keep revision actions secondary. | P2 follow-up. |

The Infographic Studio backend treats reselecting the same story as a no-op;
this review did **not** find the destructive invalidation that an action-looking
Selected button might suggest. Preserve that behavior in any UI change.

## Reviewed paths without the same defect

- **Marketing Studio shared settings:** model-routing and storage choices use
  native radio inputs in segmented groups. Buttons open studios or save/apply
  settings. No Yoodli-style rejected dependency toggle was found in these paths.
- **Blog Studio:** source choices, optional analysis, permissions and research
  refresh use native checkboxes. Writing-kind cards and angle selection are
  exclusive choices with explicit selected styling; they are not independent
  on/off settings. Finishing opens/closes a panel and remains an action button.
- **Infographic Studio:** research-first, extraction acknowledgment, CSV column
  inclusion and private-file inclusion use native checkboxes. Disabled private
  source/artwork choices have an explicit enclosing editable-project choice.
- **Shared research panel:** external search, site restrictions and Google tab
  selection use actual checkboxes.

## Evidence and next slice

Presentation Studio findings are in
[`deck-desk.js`](../../studios/presentation/skills/presentation-studio/scripts/desk/deck-desk.js)
(`startsSays`, `settingsStep`) and
[`app.js`](../../studios/presentation/skills/presentation-studio/scripts/desk/app.js)
(`noteSheet`, `slideMarks`, document classification review).
Infographic Studio's story controls are in
[`app.js`](../../studios/infographic/runner/web/app.js); same-story preservation
is in [`contracts.py`](../../studios/infographic/runner/contracts.py) `advance`.

Implement Presentation Studio's independent checkboxes and accurate checkpoint
copy first. Treat slide edit modes as a separate interaction change with explicit
selection/payload tests. Refine Infographic Studio's story selection afterward.
Keep existing project state, source scope, research cost consent and delivery
approval behavior intact. Verify keyboard, pointer, phone/desktop, selected versus
focused states and reduced effects using disposable native-page fixtures.
