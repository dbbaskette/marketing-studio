# Editorial desk access, phone layouts and continuation — runtime 1.12.2

Implements #56 and #58, followed by #53 and #59, on main's `2913120` base.
The installed runtime and both distributions are rebuilt; guidance minimum and
Hub schemas remain unchanged. Run the latest trusted installer to update helpers.

## Behavior and boundaries

- Notes, contexts and writing rules retain their supported editor. Decisions,
  collections, candidate lessons and conflicted/old memory revisions open
  read-only with a specific explanation and continuation. The backend refuses
  converting a decision through the note editor or editing specialized records.
- Refresh uses the Hub's existing read-access, repository identity/privacy and
  immutable-history checks. Actual writes reverify write permission under the
  workspace lock. The access panel distinguishes no Hub, verified write,
  read-only, expired/missing authentication and unavailable verification. It
  explains unavailable controls before data entry; cached browsing remains useful.
- At 800px and below, the same table data becomes labeled stacked rows. All four
  views retain their essential information and actions without sideways scrolling.
  Desktop tables remain. Navigation and actions are at least 44px high; dialogs
  scroll internally with sticky Close and Save controls. Independent views no
  longer carry misleading step numbers.
- Article details read only the selected bounded manuscript preview. They show
  review freshness, stop point and actual next action rather than blindly using
  a stale intake message. Changed readiness/publication decisions, conflicts and
  newer shared revisions have explicit explanations. Shared reviews are snapshots
  needing local verification, not a fresh review verdict.
- Attention items open their exact finding, article and selected evidence. Their
  identity is checked against current saved findings; obsolete selections must
  reload. Inbox search filters before pagination. Editorial fields, reviews and
  evidence/history are separate secondary disclosures.
- Copyable requests contain the article identity and retain the requested stop.
  Clipboard denial leaves selectable text. Reading/copying does not edit a draft,
  advance writing, approve publication, change Google documents or grant access.
  Existing view/filter state stays behind the dialog. No deep-link/navigation API
  or new session-authentication exception is introduced.

## Evidence

Targeted backend checks cover local/Hub preview bounds, empty/draft/outline/ready/
stale/conflict states, exact finding/evidence identity, no-match inbox search,
read-only refresh, rejected writes, provider authentication/transport failures,
identity/privacy changes and supported/specialized memory kinds. The Node harness
executes actual desk functions for capability controls, read-only details,
article/finding disclosures, clipboard fallback and existing concurrency/receipt
contracts. Both new GET routes retain session/Host/origin authentication.

A real headless Chromium run against a disposable local FakeProvider desk checked
**320, 390, 768 and 1440px**, each with all four views. It verified no document/cell
overflow, navigation/action targets of at least 44px, internal dialog scrolling
and visible Close/Save, read-only decision details, disclosure defaults,
article-specific finding continuation, clipboard-denial fallback and zero browser
errors. Long fictional titles, overdue dates, stale readiness and saved Google
links were included. Screenshots were inspected and the author guide was updated.
The initial browser fixture had an incomplete collection config; it was corrected
before the successful run. A notice replacing a state explanation was repaired
and the full browser check passed again.

Full compatibility verification uses the exact PR head with the existing native
Tart Linux/macOS × Python 3.11/3.13 workflow. Its GitHub check results and cell logs
are the publication evidence; no existing pass is attributed to a changed head.
Local targeted/browser diagnostics are under `/private/tmp/desk-details-tests.log`
and `/private/tmp/blog-studio-desk-browser-results.json`.

This is synthetic/disposable verification. It does not complete real account,
Google, multi-member or participating-team acceptance, and it makes no measured
performance improvement claim. Team content, credentials and local diagnostics
remain outside the skill repository.
