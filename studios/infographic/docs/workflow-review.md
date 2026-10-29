# Infographic Studio planning and delivery review

This review follows a generated response from captured source material through
fact validation, story selection, composition, editing, actual-page inspection,
approval and delivery. Synthetic material and injected provider responses keep
verification separate from signed-in provider acceptance.

## Findings resolved

| Boundary | Failure found | Resolution |
| --- | --- | --- |
| Source → fact | A normal paraphrase was stored as a literal source value and rejected. | Preserve the assertion wording and locate its literal value in its verified quotation. Manual fact adoption remains strict. |
| Quotation → location | Line breaks, nonbreaking spaces, composed Unicode and quotation typography prevented unique literal matches. | Match only unique whitespace/typographic equivalents and retain the original source slice and character offsets. Absent or ambiguous evidence still fails. |
| Model → measurements | Exact numeric strings, missing context fields and display precision differed from native records. | Canonicalize only source-backed quantities or explicit calculations; retain literal source precision. Unknown context stays unknown. |
| Facts → calculations | Reproducible dependent facts could arrive before operands or omit derivable metadata. | Verify operands first, resolve the dependency graph, infer only the operation's defined unit and identical operand context, then rerun native arithmetic validation. |
| Alternatives → selection | One unsupported generated assertion could discard unrelated supported alternatives. | Only verified facts and fully valid alternatives reach selection. Requirements, locked wording, exclusions and omission rules still apply. |
| Source exclusions → brief coverage | Generated plans put optional source exclusions into omitted requirement IDs, blocking briefs with no must-show requirements. | Preserve those optional notes in qualifications; bind generated omission and coverage fields to actual brief requirement IDs. Real required omissions still block selection. Saved responses can recover locally. |
| Selection → composition | Qualitative forms became headings and paragraphs, even when called diagrams. | Build editable process flows, component maps, comparisons and pictograms. Try fitting visual arrangements and readable type sizes before requesting prioritization; never silently fall back to a paragraph page or discard text. |
| Image worker → local output | The adapter looked only in its job folder while native Codex saved output beneath its recorded thread. | Bind output collection to the exact system-reported thread UUID. Recover completed saved output locally, preserve immutable receipts, reject stale/cancelled/linked output and never resubmit on refresh. |
| Generation → iteration | An image worker could request corrective variants within one intent. | Request one generation per explicit intent; later revisions remain explicit and separately recorded. |
| Diagram → editing | Exact-size title boxes blocked a reasonable wrapped edit. | Reserve two readable title/label lines; retain complete accessible SVG labels across wrapped spans. |
| Composition → checks | Generated process ordinals were treated as unsupported numeric assertions; pre-numbered titles were duplicated. | Apply the compositor's expected ordinal once and exclude only that structural prefix from assertion checks. Other numbers remain checked. |
| Measurements → render | An all-zero series passed evidence checks but failed positive-scale rendering. | Render exact zero labels with zero-length marks; signed values require number callouts instead of proportional bars. |
| Failure → recovery | Valid JSON responses disappeared after validation failure; another attempt spent allowance again. | Retain private, revision-bound responses before validation. Recheck locally; make a new assistant request only through an explicit fresh action. |
| Recovery → browser | Refresh left a failed plan in the library, and action failures could leave stale client revisions after partially saved work. | Reopen pending saved plans, expose captured-source review, and refresh saved state after action failures. |
| Recovery → sharing | Retained responses add private material outside the approved delivery. | Keep responses under private jobs, bind them to owner/source/brief/revision, check digest and paths, and exclude them from every sharing inventory. |
| Story → artwork → inspection | Free-form JSON at later authoring steps could repeat the same shape failures; malformed reference fields could raise type errors. | Give Codex bounded art-direction and inspection schemas with owned region/asset IDs. Validate malformed art, review and scoped-revision fields before changing the page. |

## Regression coverage

`tests/workflow_cases.py` supplies raw provider-shaped responses rather than
prevalidated native records. Fifteen cases cover paraphrases, evidence-linked
diagram nodes and connections, descriptive
comparisons and components, processes, whitespace, quotation typography,
timelines, numeric strings, zero measurements, calculations, signed callouts,
attached units and partly unsupported alternatives.

The native workflow matrix feeds JSONL through the real author parser, then
selects, builds, records fixture inspection, checks, approves and exports each
case. Negative cases cover changed quantities, invented dates, ambiguous quotes,
unreadable or tampered retained responses, links, interrupted writes, stale
briefs, invalid fresh-request flags, malformed fact/story fields and accidental
sharing of planning records. An injected renderer is used in native unit tests;
it is not evidence of visual quality.
`tests/test_authoring_contracts.py` feeds raw art-direction and inspection replies
through the author parser and an illustrated build, then checks explicit approval.
Its synthetic image adapter and renderer exercise the contracts without claiming
image quality or calling a provider. Malformed references and scoped revisions
must produce ordinary validation failures and preserve the page.

`tests/ui/workflow-matrix.cjs` drives representative responses through the actual
phone UI and pinned renderer, including Google Doc intake and Google Doc/PDF
delivery adapters, focused editing, inspection, checks, approval and downloads.
It checks process assertions before any editing, zero rendering, measurement
precision, calculation delivery, saved-response refresh and request counts.
The normal journeys cover 320/390/1280 widths, light/dark, reduced motion,
control sizes, horizontal overflow, browser runtime errors and stale approval.
The existing activity, remote-source, private-return-link, team, image-adapter
and standalone installer checks remain part of the clean-machine suite.

## Intentional boundaries

Unlocated evidence, ambiguous formatted numbers, incompatible measurement
contexts, unsupported dates, circular/incorrect calculations and genuinely
overfull pages need a concrete source or story correction. The application must
retain work and explain that correction instead of guessing evidence, inventing
measurements, weakening approval or automatically repeating provider requests.
Arithmetic and literal matching do not establish semantic truth: a reviewer must
still inspect the actual composition and its supplied assertions. No supplied
fact is marked independently corroborated by these checks.

Synthetic tests do not establish live account capability, model behavior or
owner visual acceptance. Live planning/image generation and first-release
sign-off remain separate owner actions; this review does not close those gates.
