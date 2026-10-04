# Implementation review — October 4, 2026

Blog Studio has useful safety and continuity foundations. The next improvement
should make their results consistent across chat and the editorial desk: one
operation definition, one available-action model, one truthful save receipt, and
one bounded observation of saved Hub data per request. Keep the existing Python
standard-library runtime, small frontend, private Team Hub, and separate skill
repository.

Reviewed source: `bdd4842542e9788f4ae334fb2a57e1baa63424e4` (PR #52), with a clean
working tree before this report. This is a review and proposed delivery sequence,
not an implementation of the recommendations. No real drafts, accounts, Google
writes, membership changes, or publication were used for the diagnostic work.

## Highest-priority findings

| Priority | Finding and effect | Recommended change | Tracking |
| --- | --- | --- | --- |
| P1 | Curation has no expected-state guard. A stale form can overwrite newer source tags, notes, or retirement. | Return a source revision/fingerprint; validate it under the write lock before checkout or mutation. Keep the proposal visible on conflict. | [#57](https://github.com/dbbaskette/blog-studio/issues/57) |
| P1 | Save handlers conflate shared, queued, pending-review and partial outcomes; modal errors appear outside the modal. Memory ignores the returned save result. | Normalize existing runtime results into local-save/sharing/verification/next-action fields. Show errors inside the active dialog and retain entered data. | [#55](https://github.com/dbbaskette/blog-studio/issues/55) |
| P2 | `load()` renders using mutable global view/page state after awaiting a response. An old board response can be rendered as memory and throw. | Capture request state; use a request sequence and cancellation; ignore superseded responses and preserve current results on failure. | [#54](https://github.com/dbbaskette/blog-studio/issues/54) |
| P2 | Read-only refresh runs write authorization, and the UI offers unsupported edit actions, including decision-memory saves. | Return capability/action metadata; use read guards for refresh and write guards for mutations. Give every memory kind a supported detail view. | [#56](https://github.com/dbbaskette/blog-studio/issues/56), [#58](https://github.com/dbbaskette/blog-studio/issues/58) |
| P2 | The desk emphasizes metadata forms and table columns over continuing the selected blog. Attention actions are plain text. | Lead with working copy, blocker, and one available action; disclose metadata/history on demand. Use stacked rows on phones and an explicit article-specific chat continuation. | [#53](https://github.com/dbbaskette/blog-studio/issues/53), [#59](https://github.com/dbbaskette/blog-studio/issues/59) |
| P2 | Attention search is ineffective: the UI sends `query`, but `/api/inbox` never passes it to filtering. | Filter title/finding/kind before pagination, or remove the unsupported search control until available. Test matching and nonmatching queries. | Additional acceptance under #59; no new issue created |
| P2 | Ten local blogs trigger eleven full saved-Hub observations in one inbox request. | Share an immutable, validated local observation across the request. Keep remote refresh and pre-write guards separate. | New performance follow-up; no new issue created |
| P2 | Progressive loading budgets measure file sizes, but do not enforce entry budgets or verify actual route dependency selection. | Add explicit operation dependencies and representative route/context budget checks. Split setup/recovery from the installed entry. | New progressive-disclosure follow-up; no new issue created |

Evidence locations: [request/render handlers](../skills/blog-studio/assets/management/app.js#L18),
[save handlers](../skills/blog-studio/assets/management/app.js#L37),
[HTTP dispatch and inbox query](../skills/blog-studio/scripts/management.py#L131),
[Hub observations inside the inbox loop](../skills/blog-studio/scripts/editorial.py#L105),
and [guidance measurement](../scripts/measure_guidance.py#L26).

## Simplify the implementation

1. **Define each operation once.** Routing currently lives in prose routers,
   `author_workflow.ROUTES`, its separate global routes, argparse commands, and
   management dispatch. Introduce a small declarative operation registry with
   aliases, input schema, scope, mutation classification, minimum runtime,
   required/conditional references, and supported result states. Generate or
   validate router tables from it. Keep natural-language interpretation for
   ordinary requests; the resulting structured intent must use a known operation.
2. **Use one state/action projection.** `home`, status, board, inbox and UI details
   each interpret aspects of article state. Share a projection of manuscript
   state, explicit editorial decision, stop point, review freshness, capability
   observations and available actions. Preserve their distinctions internally;
   readers need an understandable label and next action. A passed review does
   not authorize readiness or publication.
3. **Use one receipt adapter.** Wrap existing durable runtime outcomes rather
   than inventing another sync backend. Record what was saved locally, what is
   queued/shared/pending/uncertain, and what can safely happen next. An upload
   source and its new article can have different outcomes. A check/retry should
   reuse retained operations, never create new mutations to recover an old one.
4. **Maintain one runtime source.** Bootstrap copies are legitimate distribution
   outputs, not independently maintained implementations. Packaging already
   copies canonical helpers. Centralize the repeated packaging/install runtime
   file lists and verify generated parity; keep executable integrity and trusted
   installer updates. Guidance fetches must still not execute downloaded scripts.
5. **Format the maintained source.** Dense multi-action Python lines and the
   62-line frontend obscure control flow and ownership. Expand functions by view
   and operation; separate loading, rendering and forms. Keep the plain frontend;
   no framework migration is justified by this review.

## Measured performance opportunities

[Raw samples and workload](performance/editorial-review-2026-10-04.json).
Three samples per operation, macOS arm64/Python 3.14.5, cProfile enabled; ten
synthetic blogs and thirty synthetic sources in a disposable workspace, shared
through a local bare-Git FakeProvider. No live provider or model time is included.
Samples run in one prepared process; first use is not a flushed filesystem cache.

| Operation | Median | Git subprocesses per call | `validate_files` calls per call |
| --- | ---: | ---: | ---: |
| Board, ten blogs | 62 ms | 2 | 2 |
| Inbox, selected blog | 61 ms | 2 | 2 |
| Inbox, all ten blogs | 672 ms | 22 | 22 |
| Library search, thirty sources | 128 ms | 4 | 4 |

The empty ten-blog inbox still takes eleven Hub reads: each `hub_state` observes
all cached files, followed by the shared-article graph. Output pagination limits
response size, not the amount of scanning. The library's SQLite query still
starts with `source_rows` over all canonical records; resolving collection names
observes the Hub again. A changed signature rebuilds every row, and search uses
`LIKE` over prose rather than a full-text index.

Start with request-scoped Hub observation reuse and a binding-to-local-row map
(the board currently searches local rows for each mapped shared article). Then
profile larger source histories. Incremental index updates and SQLite FTS are
conditional follow-ups, justified by measured size/query needs rather than this
small fixture. Cache only validated local projections keyed to the observed
revision/outbox state; invalidate on mutations. Cached observations cannot guard
remote writes or establish live freshness.

The single-threaded `HTTPServer` performs synchronous provider work in POST
handlers. Such a call can hold up all desk reads; provider helpers have timeouts
but the browser shows no operation progress. First add explicit pending/loading
states and truthful receipts. If measured live waits justify background jobs,
use a small local job/status interface and preserve serialized writes, durable
operation IDs, and unknown-outcome reconciliation. Do not simply enable parallel
mutations to make the UI appear faster.

No optimization was implemented, so no before/after speed gain is claimed.

## Better user experience and interface

The desk should be a useful companion to the harness. A blog detail opens with
its title, author, bounded manuscript preview or verified working-copy link,
current blocker and primary continuation. A secondary “Editorial details”
disclosure contains owner, date, stage and publication URL; “Evidence and history”
contains pinned references, review coverage and previous revisions.

An attention item should open the specific finding and offer a copyable command
such as `Continue blog <id> and show its stale factual-support review` when the
harness has no supported navigation API. Do not assume clipboard or harness
navigation works; provide selectable text as fallback. Keep local-vs-shared
state, last observation and pending saves visible beyond a transient toast.

Use stacked rows/cards on narrow screens, retaining title, stage, owner/due and
working-copy action. Keep the desktop table. Avoid numbering navigation as if
these four views were workflow steps. Give dialogs their own error/status region,
clear close/save controls and comfortable touch targets. Search labels should
match supported fields per view. Replace raw technical status slugs with plain
labels, while retaining structured values in receipts.

The checked-in guide screenshot also needs a fresh visual review: the current
PNG shows clipped navigation and a very narrow content region inside a much
wider image. This is an artifact-quality finding, not evidence that every desktop
render has that geometry. Recapture desktop and phone examples after #53/#59.

**Narrowed link finding:** a raw `?tab=...` URL is rejected by the editorial link
helper, but the real handoff normalizes saved URLs to `/edit`, so this is not a
reproduced missing-link defect on that path. The normalization retains `tab_ids`
separately. When exactly one saved tab is selected, deriving a safe tab-specific
working link would improve navigation; keep multi-tab scope explicit.

## Better progressive disclosure

The checked-in entry estimate is **1,457 tokens**, above its stated 800–1,200
range. The installed bootstrap adds **1,365** on first use. The source-backed
first-draft route lists **5,797**, and quick polish **4,101**, before bootstrap,
conditional style/privacy/Hub references or author material. These are character
count divided by four estimates, not measured model tokens or bills.

`measure_guidance.py --check` detects a stale inventory; it does not fail for
exceeding those targets. Its route lists are manually chosen file sets and are
not traces of actual harness reads. The quick-edit scenario includes deliberate
extra review work, so it should not be compared with plain proofreading.

Proposed loading levels:

- **Entry:** intent, workspace/article resolution, trust boundaries and the
  instruction to obtain a focused plan. Aim for the existing 800–1,200 entry
  target and a smaller 500–800 bootstrap, then verify on real route traces.
- **Operation pack:** exactly the required references, selected manuscript and
  context pins; explicit conditional dependencies with reasons. Operational
  helpers use the installed runtime; article writing keeps its guidance pin.
- **Detail:** recovery, provider contracts, uncommon formats, comprehensive review
  and upstream methods only when a condition or explicit request calls for them.

Return required paths and conditional paths separately from the operation
registry. Track a per-session loaded-reference ledger by content hash so reuse
is observable. Do not make every hyperlink a mandatory dependency: distinguish
required instructions, conditional operations, and optional attribution. Verify
proofread, outline-only, Google return, shared resume and library search paths
against explicit reference lists and output bounds. Never trim necessary source
context or semantic review merely to meet a guidance budget.

## More deterministic operation handling

Current `route` returns a plan, not execution evidence. `proofread` is recognized;
`proofread this` returns `interpret-request`. `pull and proofread` is recognized;
`pull from google docs and then proofread` also returns `interpret-request`.
That fallback is documented and not a safety defect, but workflow sequencing
then depends on the harness reinterpreting prose consistently.

Use the registry to resolve intent to typed steps, prerequisites and receipts.
For `Pull and proofread`, the fixed transfer sequence should be capture → compare
→ resolve only if required → accept verified return → semantic proofread → save
→ report sharing result. Stop on a blocked or uncertain return; do not start
editing a stale draft. Reuse current Google plan/ledger/revision contracts rather
than introducing a second transfer engine.

Keep author intent and editorial judgment with the model. Make article identity,
stop points, dependency selection, schema validation, state transitions, exact
input/version checks, durable operation identity, retry eligibility and saved
readback deterministic. Mechanically verified quotations prove an exact match,
not that a claim is semantically supported. A context pack or cached lint result
must not manufacture a semantic review verdict.

## Audit of the new issues

No exact duplicates were found among #53–#59. They are focused refinements of
#39/#43/#44, not substitutes for the outstanding live acceptance in those issues.
Keep their acceptance criteria and tracking identities; combine implementation
where the same underlying code changes serve more than one issue.

| Delivery group | Issues | Why group them without closing duplicates |
| --- | --- | --- |
| Save correctness | #55, #57 | One receipt/error/conflict path; stale-state guards remain a separately testable acceptance outcome. |
| Request and capability model | #54, #56, #58 | Shared loading/detail/action model, but request ordering, unsupported decision editing and read-only access are distinct defects. |
| Author-facing desk | #53, #59 | Same view components and disclosures; mobile usability and correct article-specific continuation each need verification. Add inbox search coverage here. |

Recommended order: fix P1 save/concurrency outcomes first, with #54 request
ownership early enough to make subsequent UI tests reliable. Then implement
capability/detail handling and responsive continuation. Follow with a separately
measured performance/progressive-operation increment. Avoid one giant PR that
mixes transfer architecture, cache optimization and visual changes.

Keep live newcomer/harness/member/Google/team-collection acceptance separate in
#8/#9/#10/#15/#44. Existing evidence or broad epic membership does not close a
specific remaining live criterion. This report does not edit, close, duplicate,
or replace any GitHub issue.

## Verification of this review

Code inspection, the profile above, a disposable saved-Google-handoff fixture,
a real loopback HTTP request with a nonmatching inbox query, and a minimal Node
DOM stub exercising delayed responses. The old board response reproducibly threw
`Cannot read properties of undefined (reading 'level')` after the memory response.
The nonmatching inbox query returned HTTP 200 and the unchanged finding.

The initial DOM stub omitted `textCell`; that setup error was corrected before
the race result was recorded. Normalized handoff verification narrowed the raw
URL suspicion as described above. No runtime fixes, installed updates or live
provider acceptance are claimed. Repository CI remains the publication gate.
