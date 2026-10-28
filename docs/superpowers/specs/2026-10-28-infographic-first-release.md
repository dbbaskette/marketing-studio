# Infographic Studio first-release execution specification

The product contract is `docs/infographic-studio-spec.md`; the scope and acceptance
criteria are milestone 2 (#138–#143 and its 24 tasks). This execution specification
resolves interfaces without expanding that scope. Foundations merged in #178.

## User journey

Add information → choose or refine the story → build and review one page → approve
that exact revision → export. Keep source details, art direction, checks and history
available in the same desk. A conversation uses the same checked commands without
opening a browser or starting a nested planning assistant. New work never enters
the retired guided pipelines.

## Implementation decisions

- Preserve schema-1 project records, immutable version files, ownership and expected
  revisions. Extend the native store with checked content mutations, private owned
  blobs, history and atomic internal job/check/approval transitions. Do not add a
  second content authority. Restore creates a new revision without approval.
- Capture original source bytes and normalized UTF-8 text separately. UTF-8 errors
  and unsupported formats are refused. CSV preview is non-mutating; row/column,
  type and unit selections require confirmation before capture. Exact source
  locations and literal quotations are validated before evidence can be adopted.
- Assistant proposals are data, never filesystem or approval authority. Source,
  story and artwork instructions are untrusted content. All submitted facts,
  calculations, requirements and scene changes are validated deterministically.
- Pin a resolved brand snapshot to the project. Brand/default changes are explicit
  content mutations. No organization, personal path or downloaded brand is a
  default. Local brand capability failures remain actionable.
- Persist image intent and exact prompt before execution. Adapters receive owned
  attempt folders, staged references and bounded transports. Gemini alone reads
  its key; assistant and renderer environments exclude provider secrets. Codex's
  scoped image path does not change the other studios' worker capabilities.
- Unknown outcomes never automatically resubmit. Cancellation revokes adoption;
  current revision, input basis and attempt ownership are checked before landing.
  Automatic layout/image repair shares a maximum of two attempts. Explicit user
  retries create new intent and retain earlier assets and prompts.
- Deterministic scene composition preserves editable words and numeric marks.
  Images remain raster. The existing isolated Chromium renderer measures fonts,
  wrapping, decode validity, output dimensions and PDF page count. Missing fonts
  and overflowing content block approval; do not shrink away requirements.
- Checks bind all relevant inputs and the scene digest. Structural success never
  implies visual inspection. Actual-image inspection or an explicit recorded
  human review is required. Approval is a user action and includes the current
  checks. Export retries use saved approved scenes without provider work.
  The visual check also binds the exact review decision: a newer review requires
  new checks and approval, including when it arrives during final rendering.
- Reuse shared Golden Gate controls, drafting/history primitives where compatible,
  the catalog/lifecycle protocol, shared-settings authority and bundle machinery.
  Native CLI, authenticated API and browser consume the same engine methods.

## Verification and release boundary

Each coherent slice owns targeted synthetic tests. One final integration pass owns
root/native regressions, disposable Tart and source-independent bundle acceptance.
Browser checks cover desktop/phone, keyboard, light/dark and reduced effects.
Provider transports, credential lookup and subprocess runners are injected in
automated checks. No verification uses personal studio state or real providers.

Live generation/edit/inspection for each provider, actual illustration-quality
owner review, platform acceptance and release publication are distinct gates.
Do not close Q02/Q03 or mark milestone 2 complete while those gates lack evidence.
Do not solicit keys in issues. Real-user upgrades and publication are separate
instructions. Unknown/unsupported platform combinations remain explicitly named.
