# Team Hub implementation plan

Status: H1–H3 and the H4 installer/documentation slice implemented locally; real-provider/harness pilot remains pending. Contract: [Team Hub spec](../specs/2026-10-01-blog-studio-team-hub.md). User scope: shared blogs, notes, sources, voices, reviews, and user-defined rules/memory/context; separate skill repository; create and join by conversational request; members already have repository access.

## Delivery sequence

| Slice | Outcome | Depends on | Development tokens |
| --- | --- | --- | ---: |
| H1 Format + create/join | Validated shared record format; private GitHub lifecycle; managed local clone and active hub registry | Current trusted installer/runtime contract | 12–20k |
| H2 Save + sync + conflicts | Durable operation outbox; immutable revisions; idempotent/concurrent writes; branch-policy outcomes | H1 | 18–30k |
| H3 Writing + memory adapter | Shared article/source/voice/review lifecycle, scoped user context, progressive lookup, selected migration | H1–H2 | 18–28k |
| H4 Installer + pilot | Managed runtime release, newcomer paths, deterministic integration suite, authorized team pilot | H1–H3 | 10–17k |
| **Total** | **Initial Team Hub workflow** | | **58–95k** |

These are development planning ranges, not enforced token budgets or measured runtime costs. The Google Docs provider implementation remains separately planned; do not add its whole estimate to H3 merely for shared Doc metadata.

## H1 — Format, create, and join

Outcome: an explicit owner/name creates one recoverable private hub; a valid URL joins it locally. Current installer/core author data are not migrated automatically.

Proposed code: `skills/blog-studio/scripts/hub.py` for the installed trusted entry; focused supporting modules only if complexity warrants them. Existing authoritative scripts live under `skills/blog-studio/scripts/`; `scripts/package_installer.py` must add the new helper/support files to the bootstrap build and manifest. Reuse existing timeout/output/ownership conventions without treating `sync_guidance.py`’s hardcoded instruction remote as a generic data remote.

Proposed instructions: `references/hub/workflow.md`, `references/hub/setup.md`, and a concise parent capability route. Proposed docs/fixtures: `docs/team-hub-schema.md`, schema/example data under `tests/fixtures/team-hub/`, `tests/test_team_hub_lifecycle.py`.

Define schema and globally unique hub/item/revision/operation IDs; record hashes and portable references; validate item graph, text/binary limits, source identity, and compatibility. Plan an append-only revision graph and locally derived catalog rather than mutable shared indexes.

Interfaces should support `create`, `join`, `list`, `select`, and `status`. Create requires concrete owner/name and destination; join requires an explicit URL/owner-name. Persist creation intent before GitHub writes, reconcile unknown results, preserve unrelated remote/local state, and activate only validated clones. Inspect actual provider role and branch policy where available; otherwise show unverified contribution capability. Do not invite users or change membership implicitly.

Verification owner: implementer. Disposable bare/working repositories and mocked GitHub boundary responses exercise fresh/idempotent create/join, unrelated existing repo, partially completed create, ambiguous timeout, missing auth/read access, read-only member, replaced remote identity, bad schema, symlink/size violations, path with spaces, and nonempty destination preservation. A live create is deferred to the authorized pilot target.

## H2 — Durable shared writes and sync

Outcome: authorized artifacts sync with honest local/queued/published/pending/conflicted statuses and no lost revisions.

Proposed code continues `hub.py` and focused storage/sync modules if justified. Add `tests/test_team_hub_sync.py`. Implement a persistent local outbox with stable operation ID/payload hash/parent baseline, one local lock, atomic local records, and explicit lifecycle state. The remote receives only portable selected hub records/artifacts.

Interfaces: `save`/`revise`/`remember`, `sync`, `history`, `resolve`, and tombstone-based removal. Require an explicit file/item and kind/scope; do not sweep unrelated workspaces. Same ID/same payload retries reconcile; mismatched reuse fails.

Use validated remote commits and an owned staging/index to compose exact operations into a fast-forward update. Capture Git diagnostics without leaking credentials or dumping downloaded content. On contention fetch/recompose with the same operation, up to the configured bounded retry count. Independent records combine; same-item concurrent revisions form a preserved divergent graph rather than an automatically merged manuscript. Implement resolution with both parents.

Respect main protection: if reviews are required, publish an operation branch and PR, deduplicate uncertain PR creation, and report pending until the operation is fetched on the shared branch. Attach created PRs with the host artifact tool where available. Permission failures/unsupported policies keep the operation durable and actionable; no forced push or protection change.

Verification owner: implementer. Two or three disposable member clones test independent concurrent saves, same-item revision races, conflict resolution, multiple queued operations/dependencies, three-attempt contention limit, process interruptions before/after commit/push, success-with-response-loss reconciliation, wrong operation reuse, unavailable network, read-only push rejection, and protected-branch/PR state fixtures. Test retry boundaries and work preservation rather than mirroring helper internals.

## H3 — Shared Blog Studio state and selected memory

Outcome: user A saves a blog and user B can resume the same shared article with its dependencies and checkpoint; applicable team context is loaded progressively.

Proposed code: portable hub adapter around current `studio.py` operations, preserving that helper’s offline/manual contract. Existing local article/voice counters and absolute runtime/cache paths cannot simply be pushed. Serialize shared UUID revisions explicitly, retain originals/history, and map local projections to shared provenance without redefining source/review status dishonestly.

Update `references/workspace.md` and focused hub instructions for new article, source intake, profile selection, checkpoint, review, and resume. Add scoped rule/context record types and explicit request → selected article/author/project → team default precedence. Persist actual selected revisions with the article; deliberate dependency refresh stales affected checks. Store Google Doc identity/transfer references portably without claiming provider read/write implementation exists.

Interfaces: `find` with kinds/scope/tags/text/limit; `read` for exact item/revision; `context` for applicable rules and selected memory; `import-workspace` for explicitly selected existing artifacts. Return small catalog slices and paths; large source passages are read only for the current task. Build indexes locally from validated records; no external embeddings subscription or database server.

Verification owner: implementer. Exercise all six entry routes against shared state, independently joined member resume, voice/source/rule pinning, outline-only stop points, review freshness, source roles, original/history preservation, equivalent rule conflicts, unresolved article conflicts, and explicit selected migration with no unrelated uploads. Verify that machine paths/credentials/system caches are absent from published records. Add measured runtime instruction counts after the guidance exists; do not claim design targets as measured results.

## H4 — Installer, documentation, and team pilot

Outcome: existing users receive a deliberate trusted runtime update; future installs can enable hub operations without an alternate writing app.

Extend the bootstrap/runtime build and compatibility manifest. Creation needs the GitHub provider capability (initially authenticated `gh`); basic Git access alone may support clone/read, but full creation/permission diagnostics require an available provider interface. Reuse the installer’s optional GitHub CLI setup choices and keep dependency/auth changes visible. Do not make joining or writing switch accounts silently.

Update README/PACKAGE, installation/troubleshooting docs, and token inventory only after implementation. Package offline/full and bootstrap distributions together without copying hub data into either. Verify extracted-bundle operation from another directory and retain runtime rollback behavior for existing users.

Final integration verification owner: implementer. Run the full relevant deterministic suite once for the final changed tree; reuse unchanged helper evidence, run affected checks for fixes, and complete required CI. Check packaged/source consistency and quiet output limits. A final review examines create idempotency, concurrent/ambiguous writes, portable state, branch policies, and source boundaries. No delegation is assumed.

Then conduct an explicitly authorized disposable GitHub repo/member pilot: admin create, member join, shared blog save/resume, source/rule update, concurrent article conflict and resolution, offline queue/recovery, protected-branch contribution if in scope, and newcomer status comprehension. Verify real provider/harness behavior separately from fixtures. No automatic global install, collaborator invitation, branch-rule mutation, or production-memory write is part of local tests.

## Decisions recorded and remaining inputs

Recorded: Team Hub naming as working label; Git backend; first provider GitHub; separate skill repo; all read/write writing data shared by default; members already have contribute access; local clone per member; quiet progressive context loading; immutable revisions and explicit semantic conflicts; sync at task entry and meaningful saves, without a scheduler.

Implementation inputs: the actual future owner/name/local destination are requested only when a real create/join is invoked. Existing team access arrangement and branch policy must be observed at that time. Real pilot targets/accounts must be provided/authorized before live provider writes. A signed/native installer and non-GitHub providers remain follow-up options.

## Completion record

- Design: current local workspace/helper, installer update contract, and Google Docs roadmap inspected; creation/permissions/fast-forward behavior checked against primary provider documentation.
- User clarification: hub includes all read/write blogs and team working content; skill remains in a separate repo. Earlier private-draft recommendation is superseded.
- Implementation: `hub.py`, `hub_store.py`, and `hub_workspace.py`; automatic studio saves; exact historical guidance restore; focused hub references; runtime 1.1.0 installer/offline bundles.
- Verification: disposable Git/provider/member tests cover create/join recovery, queued/concurrent writes, review branches, scoped memory, and all six shared writing routes. The final suite contains 87 tests; package integrity, skill entries, and launcher syntax are checked. Results and the live-pilot boundary are recorded in Team Hub usage. No real remote hub or global install has run.

## Implementation boundary

Local runtime/guidance implementation is complete. See [Team Hub usage](../../team-hub.md) for shipped behavior and verification. The real GitHub/member and harness pilot remains pending an explicit target; Google Docs provider operations remain separately planned.
