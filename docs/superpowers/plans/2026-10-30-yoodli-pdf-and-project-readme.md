# Yoodli selection, PDF sources and project README

## Outcome and diagnosis

The requested fixes and publication are authorized. Training Studio currently
rejects the Yoodli toggle unless both dependencies were selected separately, with
the explanation at the bottom of a long form. Its fallback source picker omits
PDF even though the native document reader supports PDF. Other studio pickers
already list PDF, and shared source capture delegates extraction to the existing
bounded local reader. PDF text extraction requires installed `pdftotext`;
scanned, encrypted and damaged documents must never be presented as readable.

## Implementation

1. Make selecting Yoodli include Reference brief and Practice scenarios and update
   their visible selection. Explain the included materials beside the toggle.
   Explicitly removing a required material switches Yoodli off and explains why
   in that same location. Keep server-side dependency validation for direct API
   callers. No Yoodli account access or posting is added.
2. Include PDF in Training Studio's fallback picker. Audit the shared picker and
   each studio's source upload controls, preserving PDF extension and adding its
   MIME type for native file dialogs. Exercise selected bytes through upload and
   extraction, including unreadable/missing-reader outcomes. Preserve limits,
   authentication, originals, source scope and existing captured work.
3. Rewrite the root README around the current purpose: a local marketing content
   workbench, four independently runnable studios, shared sources/settings,
   current approval workflows, optional team sharing and explicit delivery.
   Keep installation and everyday commands concise and link detailed guides.
   Distinguish available source features from pending live release acceptance.

## State transitions

| Action | Result | Check |
| --- | --- | --- |
| Select Yoodli without dependencies | Include both materials, select Yoodli, explain locally | Actual desk script + browser |
| Turn Yoodli off | Keep explicitly visible materials selected | Desk script |
| Remove a Yoodli dependency | Remove material, turn Yoodli off, explain locally | Desk script + browser |
| Submit Yoodli selection | Native form contains both dependencies and Yoodli | Desk script + native validation |
| Choose a PDF in any studio | File dialog accepts PDF; selected bytes reach source intake | All-studio upload checks |
| PDF extraction succeeds | Retain original and readable located text | Native source checks |
| Missing reader / invalid or scanned PDF | Actionable explanation; no fabricated text or provider fallback | Extraction regressions |

## Verification and completion

Use disposable settings, workspaces, identities and synthetic PDF content. No
provider calls, Google writes, Yoodli posting or personal source reads. Run focused
UI/API/extraction checks after the complete slice; inspect a real Training Studio
form at phone/desktop sizes. Use the shared Tart runner for the full relevant
shared/Training Studio suites and package checks, reusing unchanged studio suite
evidence while checking every studio's PDF intake. Check README links and actual
CLI options. One implementer owns verification. Push a PR and merge after checks;
no application restart or software installation on the user's computer is implied.

## Completion record

Implemented. Yoodli selects and visibly retains its dependencies, explains removal
beside the control, and clears obsolete notices when selections change. Training
Studio's fallback picker includes PDF; shared and native source pickers include
the PDF MIME type. The README and linked installation/testing guidance describe
the current four-studio workbench and optional PDF reader accurately.

Full disposable macOS verification passes: shared/home 738 tests, Blog Studio
1,640, Presentation Studio 2,071, Training Studio 3,008 and Infographic Studio 185,
with package/lint checks. Two real-PDF-reader checks are skipped on that clean
environment; actual generated-PDF upload/extraction/preview passes locally through
all four native source routes with the existing reader. Missing-reader capture
preserves peers and explicitly requires attention. No reader is installed by a
test and no provider fallback is attempted.

The real Training Studio phone/desktop browser verifies Yoodli dependencies,
removal, PDF capture and the fallback picker. Final notice-clearing refinement
passes all 108 affected screen tests and the updated real browser walkthrough.
README links and CLI names are checked. All four independent/shared setup and
authenticated launch journeys pass, followed by 41-step Blog Studio Hub and
39-command shared-studio CLI journeys. Test processes and the disposable VM are
cleaned up. No user workspace or running application is changed by verification.
