# Open-issue validation — October 3, 2026

The pass reviewed all 16 open issues against merged source
`11fec533344b594aa5294d5a30e1df22196b4b93` and exercised the candidate fixes in
a disposable source checkout. Tests used synthetic material and local Git
transports. Real blogs, their selected Hub, installed skills, sharing settings, and active
editorial-desk jobs were not modified. The initial local pass used no live
writing destinations; the subsequently authorized synthetic provider checks
are recorded below.

## Findings and fixes

- **#39, shared attention inbox:** a Hub-only article still appeared as needing
  attention when every saved finding was resolved, dismissed, or applied. Shared
  review filtering now matches local filtering. A two-clone regression verifies
  closed findings disappear while unresolved findings and stale reviews remain.
- **#43, editorial readiness:** after marking a draft ready or published, editing
  `DRAFT.md` outside the helper left the local board showing the old decision as
  current. The board now compares that decision with the actual manuscript
  fingerprint and presents the changed or missing manuscript as needing review.
  Reading the board does not rewrite saved state. The regression checks both
  stages, filtering, external edits, and a removed manuscript.
- **#44, Atom article selection:** an entry's last link could replace its article
  link with a self link or enclosure. A valid scoped article could therefore be
  omitted. Discovery now selects alternate links, prefers HTML/XHTML, and treats
  an absent `rel` as alternate. Tests vary link order, media types, and default
  relations, and prevent importing entries with only self/enclosure links.
- **#44, Atom authors:** an author containing name, URI, and email was flattened
  into one incorrect author string. Discovery now takes the author's name.
- **#44, catalog resources:** the SQLite transaction context did not close the
  connection; host Python 3.14 exposed unclosed-database warnings. Catalog reads
  now close connections after both success and exceptions while retaining
  transaction handling. The regression checks release and subsequent retrieval.

Atom relation behavior follows [RFC 4287 section 4.2.7](https://www.rfc-editor.org/rfc/rfc4287.html#section-4.2.7).
Connection lifetime follows the [Python SQLite context-manager contract](https://docs.python.org/3/library/sqlite3.html#how-to-use-the-connection-context-manager).

## Issue-by-issue result

| Issue | Evidence obtained | Remaining acceptance |
| --- | --- | --- |
| [#8 — Mac newcomer setup](https://github.com/dbbaskette/blog-studio/issues/8) | Installer lifecycle, target layouts, preservation, missing prerequisites, and authentication-decline fixtures; installed Codex runtime readiness verified. | Authenticated download/browser login on a selected disposable Mac; download quarantine/trust journey; newcomer comprehension; fresh installed harness discovery. |
| [#9 — Writing routes](https://github.com/dbbaskette/blog-studio/issues/9) | Six generated prompts, local route/stopping contracts, original preservation, voice/source/guidance pins, resume, and explicit offline fallback fixtures. Codex is signed in. Claude Code is installed but signed out. | Independent live conversations, attachments and real URL intake in both harnesses; standalone voice and interview behavior; direct/generated prompt parity; actual guidance-read evidence. The authorized five-turn Codex subset passed; remaining routes and installed bootstrap discovery still need acceptance. Claude requires sign-in. |
| [#10 — Multiple-member Hub](https://github.com/dbbaskette/blog-studio/issues/10) | Two-clone local Git fixtures cover dependency preservation, conflicts/resolution, offline queues, idempotent operations, pending branches, read-only access, and generated-page protection. | A selected private disposable GitHub Hub, second already-authorized account, actual provider contribution behavior, and admin app/webhook inspection. Two local clones do not establish two real users. |
| [#11 — Google capability contract](https://github.com/dbbaskette/blog-studio/issues/11) | Current Codex connector schemas expose native read/create/edit/copy/export/comment operations, revision guards, and tab operations. `batch_update_document` does not expose a top-level suggestion `writeMode`; configured-adapter routing remains necessary. Local access/receipt contracts pass. | Selected test Doc/folder/template and audience, actual account capability reads/writes, and live Claude adapter discovery. A schema is not evidence of authorization for a particular Doc. |
| [#12 — Google intake/handoff/return](https://github.com/dbbaskette/blog-studio/issues/12) | Fixtures plus live source intake, native heading/hyperlink handoff, rejected stale provider write, actual three-way conflict, refused overwrite, explicit synthetic resolution, stale reviews, retained originals/pins/history, and guarded follow-up readback. Portable transfers were verified on private-Hub main. | Closed after live Codex acceptance. Claude capability discovery and participating-user differences remain in #11/#15. |
| [#13 — Comments/templates](https://github.com/dbbaskette/blog-studio/issues/13) | Fixtures plus native-editor verification of the anchored explanatory comment and pending suggestion; complete native three-tab template copy, nested tab, heading styling, instructions and native date retained. Only the chosen answer changed; source template stayed unchanged. Portable receipts verified on private-Hub main. | Closed after live acceptance. No dropdown-option mutation was exercised; that connector capability is unavailable. Participating-user pilot remains #15. |
| [#14 — Exports/sharing](https://github.com/dbbaskette/blog-studio/issues/14) | Supported artifact validation, refused overwrites, folder audience checks, exact permission receipts, and partial failures pass fixtures. | Native exports inspected for content/layout integrity and any explicitly selected permission-change case. No audience or sharing was changed. |
| [#15 — Marketing pilot](https://github.com/dbbaskette/blog-studio/issues/15) | Reuses the Google and Hub regression results above. | Participating users complete the real end-to-end workflow; second member and selected destinations; comprehension and actual provider differences. Fixture results cannot complete this pilot. |
| [#39 — Attention inbox](https://github.com/dbbaskette/blog-studio/issues/39) | Local findings remain visible when Google is unavailable; source/companion staleness, current-blog/Hub scope, coverage, limits, read-only fallback, and the new shared closed/open/stale finding cases are exercised. | Live Google feedback parity under #15 and conversational use under #9. |
| [#40 — Publication package](https://github.com/dbbaskette/blog-studio/issues/40) | Bound manuscript quotes, channel length flags, missing URL disclosure, retained final copy, hashes, and companion staleness are exercised. Nothing is sent. | Closed after saved-draft semantic review, Word/PDF content and heading checks, PDF visual QA, exact provenance/length readback, and verified private-Hub save. Sharing acceptance remains separate in #14. |
| [#41 — Visual companion](https://github.com/dbbaskette/blog-studio/issues/41) | Portable diagram/table/screenshot-plan records, exact grounding, caption/alt/placement, prohibited executable directives, retained output, and tamper/draft staleness are exercised. | Closed after live Codex relevance/readback verification of the portable diagram. No finished raster image was requested or claimed. General harness parity remains #9. |
| [#42 — Claim evidence](https://github.com/dbbaskette/blog-studio/issues/42) | Exact manuscript/source passages, pinned old sources, reference-role restrictions, explicit statuses, provenance hashes, and stale coverage are exercised. | Closed after live supplied-source semantic verification. Unmeasured speed was correctly insufficient, not falsely contradicted. Changeable real-world claims still require their own verification. General harness parity remains #9. |
| [#43 — Editorial board](https://github.com/dbbaskette/blog-studio/issues/43) | Explicit ownership/stages/dates, filtered/paged browsing, shared generated pages, manual-edit guards, historical source pins, and the new external-edit readiness regression pass. | Real multiple-member Hub behavior under #10 and conversational use under #9. |
| [#44 — Historical library](https://github.com/dbbaskette/blog-studio/issues/44) | Generic teams, feed/sitemap/archive/export discovery, scoped/public network guards, identity/deduplication, changed/retired sources, batched retries and sharing recovery, lessons/promotion/staleness, index reconstruction, new Atom cases, and connection cleanup pass. The 500-post local acceptance workload completed. | A participating team's explicitly selected bounded collection/site and real member reconstruction. Existing limits remain: PDFs need host extraction; archive candidates need curation; nested sitemap indexes need separately scoped post sitemaps. |
| [#29 — Editorial epic](https://github.com/dbbaskette/blog-studio/issues/29) | Aggregates the #39–#44 evidence. | Child live acceptance and the team-selected library pilot. |
| [#3 — Roadmap](https://github.com/dbbaskette/blog-studio/issues/3) | Aggregates the relevant implementation, regression, packaging, and readiness evidence. | Open live acceptance above. |

Issues #12, #13, #40, #41 and #42 were closed after live acceptance and explicit
user authorization. The other 11 issues remain open. Fixes for #39/#43/#44 are
local review candidates, not committed or pushed; neither a release nor an
installed-runtime update occurred. No GitHub evidence comments were published.

## Verification

- Baseline: **254 tests passed** on macOS with Python **3.14.5**, in 126.492 seconds.
- Final affected slice: **23 tests passed**, in 13.396 seconds, with no
  unclosed-database warnings.
- Final full suite: **258 tests passed**, in 128.688 seconds, on the candidate
  including all fixes and rebuilt distributions.
- Both skill validators, guidance inventory check, newcomer prompt checks,
  installer shell syntax, and patch whitespace checks passed.
- Full-skill and installer distributions were rebuilt; bootstrap scripts and
  integrity manifest include the fixes. These are local review candidates.
- Existing [baseline CI](https://github.com/dbbaskette/blog-studio/actions/runs/37157362024)
  passed Linux/macOS on Python 3.11/3.13 for `11fec53`. That CI result is reused
  for the unchanged baseline; it does not claim the candidate fixes ran remotely.

Additional local acceptance inspected publication-copy readback and portable
diagram, table, and screenshot-plan output, including alt text and illustrative
labels. All three retained the manuscript. Changing the manuscript then marked
both publication and visual companions stale. No rendered image was claimed.

The resource regression initially used an input that failed during filter
construction instead of at the SQLite binding step. The test fixture was
corrected; the production connection-lifetime fix did not change.

## 500-post synthetic acceptance workload

Twenty batches of 25 imported all 500 synthetic posts with no failures or pending
extraction. Original source/metadata retention used 3,414,340 bytes; the rebuilt
index used 2,060,288 bytes. Import took 2.768 seconds, initial catalog retrieval
0.101 seconds, and cached retrieval 0.078 seconds. The three-result response was
2,402 characters; the requested passage selection was 45 characters under a
200-character limit. Removing and rebuilding the local index preserved discovery.

These are host fixture observations with short fictional posts, not guarantees
for real websites, full-length collections, Google latency, or model billing.

## Authorized live continuation

The user approved disposable private Hub/Google assets containing synthetic writing
and live CLI conversations using the existing model allowance. All live content was
fictional. Existing real blogs and their selected Hub were not imported.

### Codex

Codex 0.159.0-alpha.12.1 completed all five fresh conversations in the repository's
live-writing runner using a project-local full offline skill. The skill-tree hash was
`54e43493dbb5f14c7f59f4db3fefae6d95938df7d85dc0bc81d36ae2255732f1`.
Outline stopping, draft adoption, preference correction, forgetting without a draft
rewrite, and immutable original preservation all passed. Transcript and manuscript
inspection confirmed the supplied six-note/two-owner observation was retained and
no delivery-speed or revenue outcome was invented.

A separate live conversation created and reopened claim evidence and a portable
Mermaid visual companion. Two claims were supported by exact supplied passages;
an unmeasured delivery-speed claim was insufficient evidence, not established false.
The visual was relevant, explicitly illustrative/proposed, and included placement,
caption and alt text. Manuscript/original/draft stayed byte-identical. Evidence and
visual code are unchanged from merged main. Issues #41/#42 were closed and their
closed state was read back. No finished raster image was requested or claimed.

These runs do not establish installed bootstrap discovery, all six independent
writing routes, standalone voice, uploaded attachment/URL behavior, guidance
refresh/offline interaction, or Claude parity. Claude Code 2.1.197 remained signed
out on the final authentication check; no account setup was changed.

### GitHub and Google

- Created and verified a private disposable Hub with fresh identity and write
  access. Native Google intake and its guidance binding were saved on shared main;
  queue, conflict and pending-review counts were zero. This is one real account,
  not a completed multiple-member pilot.
- Created an isolated Drive folder under the existing ChatGPT folder and a native
  synthetic Doc. Metadata readback confirmed owner-only access. Native heading
  levels, exact manuscript text, revision guards and selected tab readback passed.
- Captured native structure plus Markdown/DOCX and inspected their text/heading
  roles before marking the snapshot structurally verified. Imported the original
  Doc as the editing destination, retaining original, draft, formatted history,
  transfer identity, baseline hashes and guidance pin in the disposable Hub.
- Created one quoted Drive comment and read it back. This establishes quoted
  document-level feedback, not a native inline anchor.
- Used the installed, already configured gcloud suggestions adapter for one small
  synthetic proposed wording edit. Actual readback reported `verified-pending`,
  unchanged accepted text, one pending suggestion and a verified native anchored
  explanatory comment. The connector itself still lacks top-level `writeMode`.
  A planning attempt initially used an incorrect test offset; it was refused before
  any write and corrected from the observed paragraph index.
- Captured pending review using the explicit suggestions-excluded native preview.
  Accepted Markdown retained “reviewed”; DOCX contained proposed “examined”. This
  confirms why DOCX alone must not be treated as accepted text. Native headings
  and formatting matched; comment/suggestion counts stayed separate. The only
  baseline text difference was two export-added trailing spaces. That inspected
  normalization was saved through exact compare/accept without accepting or
  rejecting any Google suggestion.
- Exported PDF through the installed adapter and inspected its rendered page.
  Content, heading hierarchy, spacing and page bounds passed visual QA. The DOCX
  was also inspected for content and native heading roles.
- Copied the native synthetic Doc into the selected isolated folder. Readback
  confirmed its single-tab topology, text and heading styles, and owner-only access.
  At that stage, this did not establish multi-tab or native-control template fidelity; the follow-up below does.

The linked handoff/hyperlink, concurrent-edit and native template acceptance
was completed in the follow-up below. Remaining Google acceptance includes
intended sharing cases, Claude discovery, and participating marketing users. No recipients were invited and no sharing settings were changed.
The second-member identity/access choice and human Claude sign-in were requested.
No assumption of participation or permission is made while those answers are pending.

Raw transcripts, provider identities, plans and receipts stay local. The private
synthetic destinations are recorded in the local live-provider manifest, not
embedded in this repository report. Reuse the 258-test source evidence above:
only this report changed after the successful suite; no executable change was
introduced by the live checks.

## Publication-package follow-up — October 4 UTC

Issue #40 was tested with the existing synthetic article and closed; its closed
state was read back. The installed helper assembled final Markdown, LinkedIn/X
copy, summary, metadata and working/output references in the selected private
Hub. Exact saved-draft provenance was retained; original and draft stayed
byte-identical and the article remained a draft. The package was explicitly
prepared for review, with a missing live publication URL flag. Nothing was posted
or sent to a publication channel and no document permissions changed.

Semantic review confirmed the six-note/two-missing-owner observation and the
proposed nature of the checklist. No delivery-speed or revenue benefit was added.
LinkedIn, X and summary copy measured 230, 174 and 156 characters under explicit
synthetic acceptance caps of 1000, 280 and 300. These caps are test constraints,
not a claim about current platform maximums. Metadata's limit remained unknown.

The authorized native accepted-text copy matched the saved article after
inspected trailing-whitespace export normalization. A stable capture exported
Word; native/Word headings and exact prose were inspected. The PDF export's
rendered page passed visual QA. Output references and limitations were retained
in the package notes and private receipt. Existing fixture evidence covers
length violations, missing links and manuscript/companion staleness. The package
function is unchanged from merged main, so the successful 258-test suite and
23-test editorial slice were reused; no functional source change was made.

Other candidates remain open: #39/#43/#44 include unpublished local fixes;
#12/#13 were subsequently closed after the follow-up below; #14 needs a selected
sharing case. Claude sign-in, a second authorized participant, a bounded team-selected
historical collection, and newcomer/marketing participation remain required for
their respective pilot issues. Aggregates #3/#29 remain open.


## Google round-trip and template follow-up — October 4 UTC

Issues #12 and #13 were closed and their closed states read back after actual
disposable-provider acceptance. The installed managed runtime, source implementation,
and distribution contents were unchanged. The successful 258-test suite and
package/guidance checks above remain the applicable source evidence.

For #12, a supplied-source draft was frozen before creating its native editing
copy in the selected owner-only folder. Readback and Word inspection retained
HEADING_1/HEADING_2 and the exact hyperlink target. The native Markdown projection
used angle brackets around the same URL. Confirmation correctly refused that
byte mismatch. Inspection proved only link syntax differed; the synthetic local
editing copy was reconciled to the actual projection and a fresh matching
checkpoint confirmed. The original remained byte-identical. Actual selected-tab
source intake retained document identity, URL, revision, tab and reference purpose.

The test then changed the local proposed next step and independently inserted
“synthetic” in the Google observation. A provider write using the old required
revision failed with INVALID_ARGUMENT; the rejected text was absent on native
readback. Comparison produced the baseline and both changed copies, and import
without a resolution refused to overwrite the local draft. A stale comparison
fingerprint also refused import. The disposable test-author decision explicitly
kept both fixture edits; this did not resolve any real-blog author conflict.

That return saved a new local/shared version while retaining the original,
source/voice/guidance pins, stop point and formatted history. The earlier
proofreading check became stale. The merged copy correctly remained local-only
until a freshly prepared, revision-guarded paragraph update sent it back. Actual
final Markdown matched the selected merge byte-for-byte; native/Word headings and
the hyperlink survived. Final compare returned unchanged. The private Hub's
actual main revision matched the helper receipt, and stored transfer and receipt
records were read back with relative history paths and no local paths or credentials.

For #13, the native Google editor visibly showed the struck-through “reviewed”,
proposed “examined”, the explanatory comment beside that wording, and Accept/Reject
controls. Neither control was clicked. Comment readback retained the exact quote
and live thread identity; native visibility, rather than an API custom anchor,
established the inline result. Both threads remained unresolved with no replies;
review completion remained separate from publication approval.

A native template with Draft, nested Sources, and Instructions tabs was copied
as a whole. Full-scope readback and the trusted file-backed bridge confirmed all
tabs and parent/order relationships, named/local styles, instructions and the
native date chip. The guarded edit replaced only the answer placeholder. Full
readback proved other tabs unchanged, unchanged heading/style and date properties,
and unchanged source-template revision. The editor visibly confirmed the nested
tabs, custom heading and native date. Metadata confirmed the selected folder and
owner-only access. No dropdown mutation was attempted or claimed: its metadata
and update tools are unavailable in this connector. The complete supplied
template, including its native control, was preserved without rebuilding it.

Current pinned guidance estimates use the checked-in character-count/4 method:
router 394, source 631, handoff 835, return 899, review 779, template 725 tokens.
Each focused guide meets the corresponding issue target. Provider preservation,
adapter/checkpoint/privacy references and actual document content are additional
conditional costs; these are estimates, not billing measurements.

Private raw evidence, fixture decisions and provider identities remain in the
local acceptance directory. No executable change, sharing change, invitation,
suggestion acceptance/rejection, or publication occurred in this follow-up.
