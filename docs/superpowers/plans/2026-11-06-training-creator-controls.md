# Training Studio creator controls

Issues: #396 (optional research warnings), #397 (short practice descriptions).
Implement, verify, and merge each issue before starting the next.

## Research choices

Offer Include, Include with warning, and Exclude with no preselection. Keep
independent verdicts and creator decisions in the evidence and receipt. New
receipts use schema 2; schema 1 reconstructs byte for byte, with its existing
include value still meaning include with warning. Only selected warnings reach
the report, reference brief and material author. Exclusions remove dependent claims.

## Practice intent

Default to Let AI choose scenarios. Define scenarios accepts short descriptions;
AI expands the role, goals, dialogue and evaluation detail. Persist the choice in
intake and settings and carry it through planning, practice and Yoodli output.
Existing trainings keep AI planning. Do not replace user-authored scenario files.

## State-transition matrix

| Input / state | Result | Regression |
| --- | --- | --- |
| Flagged draft + Include | Original prose/citations, separate audit, paused until Continue | shared decisions + native save/continue |
| Mixed warning/plain choices | Selected warnings propagate to dependent content; clean choices retain audit | shared dependency test |
| Exclusion + included parent | Exclusion wins; dependent passages omitted | shared decisions |
| Existing schema 1 receipt | Identical content and hashes; no reinterpretation | frozen legacy file hashes |
| Missing scenario choice | Existing AI planning, no new state or work | form compatibility |
| Define scenarios + short descriptions | Stable scenario IDs persist; every requested ID reaches blueprint, scenario and Yoodli inputs | practice intent + author contract |
| Description edit with unchanged blueprint wording | Its scenario and Yoodli inputs change; existing text is preserved | direct material-input regression |
| Scenario-only settings edit | Keep research; hold old materials; no worker starts on save; stale forms refused | settings regression |
| New intake saved/reloaded | Keep mode, descriptions and IDs, including after toggling AI | browser journey |
| Stale or active decision form | Refuse without publication or new jobs | native decisions |

## Verification

Use disposable helper/workspace fixtures, native API/browser journeys and the full
relevant local suite. No real trainings, provider calls or application restart.

Research-choice verification: 1,075 shared tests and 3,218 Training Studio tests
passed in a disposable macOS Tart VM, plus package validation and the actual
phone/desktop creator-decision journey. Legacy receipt hashes remain identical.

Scenario verification: the full 3,223-test Training Studio run exercised the new
feature in Tart. Its only failures were two old request-payload expectations for
the added default AI choice; both were corrected and passed on rerun. A subsequent
702-test run covered the material-input delta and affected workspace, draft,
settings, pipeline, worker and UI modules; it had the same two stale expectations.
The final 33-test run passed those corrections and the complete settings module;
package validation passed. The per-scenario input regression is included in the
702-test run. An additional 47 shared UI checks and the real phone/desktop intake
and settings browser journeys passed. Test workspaces and workers were disposable;
no real provider jobs or user trainings were used. Both test VMs were deleted.
