# Git-backed Team Hub design

Status: approved design, implemented locally. Read/write working state, including blogs, is shared across the team. The skill remains in a separate repository. The completion boundary below distinguishes deterministic verification from the pending real team pilot.

## Outcome and scope

A team admin asks Blog Studio to create a named private Team Hub in an explicitly selected GitHub account/organization. The skill prepares the hub, creates the remote, makes a local clone, initializes and verifies it, and selects it locally. A member with existing repository access asks to join by URL; the skill clones/registers it and makes shared memory available to normal writing tasks. Users should not need Git commands.

Team membership and contribution permission are prerequisites supplied outside the join flow. Creating a repo in an organization does not prove that an existing team has write access to that new repo. Creation must check the intended access arrangement and report readiness; it must not silently invite users, bind a team, change organization settings, or override branch rules. If a specific existing-team binding is requested as part of a future create operation, include that named binding in its reviewed scope and verify it separately.

Share all writing artifacts in the selected hub: articles/blogs and versions; briefs/outlines/interviews; working notes and decisions; sources and selected originals; author/brand voices; review findings and freshness inputs; user-defined memory/context/rules; requested derivatives; and external document references/synchronization baselines. Raw conversation/tool transcripts, credentials, absolute machine paths, caches, locks, generated indexes, and instruction snapshots are system state and remain outside shared content.

No hosted memory service, vector database, account invitation system, scheduled background sync, Git LFS bootstrap, arbitrary Git host support, live Google integration, or automatic history rewrite is included in the first release. GitHub is the first provider; keep the record format independent of GitHub.

## User operations

**Create:** obtain a concrete `owner/repo`, hub display name, and local destination. Default private visibility and main branch. Prepare initial content locally before creating a remote. Reuse the user’s authenticated GitHub access; verify owner/organization creation permission. Create only that repo, seed its manifest/data layout, push, read back, clone/register, and show its actual URL. The instruction to create that specific hub authorizes its creation/seed push; no second mechanical confirmation is required. No real owner/name is inferred from the planning examples.

Persist the logical creation ID before the remote side effect. On timeout, inspect the exact remote name and persisted identity before retrying. An unrelated existing repo must never be initialized/overwritten by accident. Report partial outcomes distinctly: remote created but seed/local registration incomplete can be recovered, not treated as no remote. A retry resumes the same intent rather than picking another name or creating another hub.

**Join:** accept a canonical GitHub repo URL or explicit owner/name, normalize identity, reject credential-bearing/unsupported URLs, and check actual Git read access. Inspect metadata/manifest and verify private visibility, hub UUID/schema, and branch before activation. Determine provider write permission and branch contribution policy when tools expose them; otherwise mark contribution readiness unverified until an actual successful push. Read-only users can read a hub but are clearly identified. Do not equate organization membership or a successful clone with contribution permission.

Clone into an absent managed destination; reuse a registered matching clone idempotently. Preserve and report nonempty/unowned locations. Register only after validating the initial snapshot. The local registry binds hub UUID, canonical repo/provider ID when available, and local storage; matching a name alone is insufficient if a remote was replaced or transferred unexpectedly. Joining changes only local selection and clone state, not membership.

**Use/select/status:** support multiple joined hubs but one explicitly selected hub per writing project/task. Selection is local configuration. The assistant never searches unrelated home folders or silently picks between matching hubs. Status returns concise freshness, revision, contribution capability, queue/conflict counts, and selected paths.

**Save/remember:** save a concrete artifact or user-chosen context/rule in the active hub. In hub mode, normal persistence at meaningful checkpoints includes shared synchronization. This is standing authorization limited to the selected working state and repo; it is not permission to publish a blog, alter sharing settings, or share unrelated files. Show content first when the assistant is proposing a new memory rather than fulfilling an explicit save/remember instruction. Import pre-existing local articles/sources/voices only when selected.

**Sync/resume:** refresh at task entry and before writing; reuse the task’s selected baseline through its operation. Resume retrieves the latest known shared article revision and its pinned dependencies, while exposing changes since the local baseline. Preserve task guidance pins independently. `refresh context` deliberately adopts newer sources/rules/voice revisions and stales affected reviews. Save/sync reports local saved, queued offline, published, pending review, or conflicted accurately.

## Storage model

Recommended root layout for the remote:

```text
hub.json
README.md
memory/items/<item-uuid>/revisions/<revision-uuid>/record.json
memory/items/<item-uuid>/revisions/<revision-uuid>/BODY.md
memory/items/<item-uuid>/revisions/<revision-uuid>/artifacts/<allowed-name>
```

`hub.json` carries schema, stable hub UUID/name, approved content branch, minimum compatible runtime, and nonsecret hub settings. Item kinds initially cover article, source, voice, note, decision, rule, context, and review. Article revisions can hold the complete checkpoint bundle: brief, outline, draft, interview/decisions, original reference, dependency/review references, stage, and next step. Derived content is a linked record or artifact; it never overwrites a manuscript.

Every revision records its item/kind/revision/operation IDs, parent revision IDs, title/scope/tags, author attribution, timestamp, content hashes, status, provenance, and typed dependency references. Global UUIDs avoid colliding per-computer integer revision counters. A revision is immutable once published. A resolution revision can name both divergent parents; a removal is a tombstone revision, preserving history. Revision labels and timestamps support display, not last-writer authority.

There is no hand-edited global catalog/current pointer touched by every save. Derive item heads and a search catalog locally from the revision graph. One unambiguous non-tombstoned head is current. Multiple live heads are a semantic conflict. Show a previous unambiguous baseline with a conflict marker, or ask the author to select a branch; never silently choose a head as an approved rule or canonical draft. Full bodies and provenance remain available behind summaries.

Graph validation checks unique IDs, hash integrity, matching item/kind, parent existence, acyclicity, legal references, and file/path/size limits. Unknown future schema fails with a compatible-runtime update message. Text records must be UTF-8 regular files; reject symlinks, path escapes, executable artifacts, and unsupported schemas before activation. Binary originals are allowed only in typed artifact slots with limits; large media should use a referenced artifact store/Google Drive rather than introducing unlimited Git binaries. Initial policy proposal: 1 MiB per memory text file, 10 MiB per selected binary, 100 MiB aggregate accepted working snapshot; limits must be clearly diagnosed and exercised, then adjusted from pilot evidence.

Local storage has a managed Git clone, generated validated snapshots/catalog, local lock, and persistent outbox. A bare clone with controlled readable snapshots is recommended so remote files never become an executable project or skill root. This is still a local clone; ordinary users see the relevant readable artifacts through the harness. A standard working checkout is an alternative, but requires handling dirty files and untrusted checkout content. First implementation should use the managed bare clone and owned staging/index for writes.

Never stage the existing `.blog-studio` folder wholesale. Its current session records include local runtime paths and cache/task details. Use an explicit hub serializer/adapter to publish portable artifacts and provenance, keeping machine-specific bookkeeping local. Local projections may reuse `studio.py` schema/operations where sound; published IDs and revision semantics remain globally stable. User content is shared by default despite local projections and outbox storage.

## Synchronization and concurrency

Use installed trusted runtime code, explicit argument arrays, captured/sanitized Git output, bounded subprocesses, local locks, and disabled hooks. Do not execute any code, hooks, `AGENTS.md`, or skill entry from the hub. Decode only validated hub records and requested artifacts. Configured team rules are selected preferences/context, not system instruction authority.

For a share operation, persist its UUID, exact payload hash, hub identity, intended parent revisions, and state before any push. Queue records survive process interruption. Same ID/same payload is an idempotent retry; same ID/different payload is rejected. An uncertain push is reconciled by fetching and checking whether the exact operation exists remotely before retrying.

Fetch current remote state, validate it, and combine independent appended revisions into a commit containing both existing remote content and the exact queued operation. Use fast-forward push without force. If another writer advances main, fetch/rebuild/retry the same operation up to a bounded limit (proposed three attempts), then retain queued state and report contention. Do not use an automatic textual merge of blog prose or change operation IDs to bypass conflicts.

Different-item additions naturally compose. Same-item revisions based on the same parent retain both branches; publish their graph when permitted but mark the item conflicted. Resolution requires a selected/reconciled artifact with both parents, preserving originals and intermediate revisions. Review records identify the exact article and dependency revisions they checked; changed/adopted inputs become stale, and unresolved conflicts never imply a clean/current review.

If the configured branch requires PRs, use an operation-specific contribution branch and PR; attach created PRs in the host when supported. The operation remains pending until merged and fetched into the shared branch. Reconcile unknown PR creation by branch/operation ID before retrying. Branch restrictions/access errors preserve the queue; do not modify protection or force a write. Users are informed of the hub’s contribution mode during create/join. The basic novice flow favors direct bounded append writes when the admin’s actual policy permits them; governed hubs can use review.

Offline reads use the last verified snapshot with explicit freshness. Offline writes are durably saved locally and queued; they are not reported as shared. A subsequent explicit sync or normal authorized task checkpoint attempts delivery. No background scheduler is installed by joining.

## Rules, memory selection, and authority

User-defined context/rules have team, project, author, or article scope, with applicability, provenance and status. Resolution order below system/developer instructions is explicit current request, article/task selections, author/project selections, then team defaults. Conflicting equally applicable rules are surfaced rather than silently ordered by timestamp. A rule’s stored priority cannot elevate its authority above the user/harness or broaden authorized external actions.

Load a small relevant catalog slice first: item IDs, kinds, titles, scope, tags, summary, status, and revision/path. Then read exact selected bodies/passages. Rule conflicts and source freshness are visible. Summaries support discovery but are insufficient evidence for precise factual checks. Do not serialize every team blog into every prompt. No hosted embeddings service is needed in the first version; use a derived local metadata/text search index from validated records.

Record the actual selected hub commit and item revisions with each task/article, alongside skill-guidance commit and runtime compatibility. Shared article portability stores instruction repo/revision and needed logical references, not another user’s absolute runtime/cache path. Existing local runtime versions can be selected for execution where installed; missing compatible runtimes get actionable setup guidance rather than a claim of identical recovery.

## Access and Google Docs

GitHub repository permissions are the access boundary. A role stored in `hub.json` or a forged commit author is not proof of provider authority. Git history provides version/attribution records, not a guarantee that remembered facts or claimed approval are true. Administrative settings and approval policy follow the actual provider role/branch policy; file-specific admin permissions are not promised without appropriate provider enforcement.

Members use their own credentials in the existing credential store. Do not copy tokens, private keys, or credential-bearing URLs into the hub. Leaving locally unregisters the hub and preserves pending/user work by default; it does not revoke server membership or erase already cloned data. Archiving/deleting/revoking access are separately requested admin operations. Tombstoning memory does not erase it from Git history; history purging is outside the initial feature.

Google Docs can become a collaborative editing surface attached to a shared article. Store canonical Doc ID/URL, relevant tabs, observed provider revision, shared article revision at transfer, and verification state. The existing Google roadmap’s handoff/return conflict logic should use that shared article baseline. Hub membership does not grant Google Doc access; preserve Google’s permissions unless a sharing change is explicitly requested. Live Google writes remain a separate implementation phase.

## Acceptance

1. An admin’s explicit create request produces one private remote and one validated local clone, with retriable partial creation state and real observed URLs.
2. A preauthorized member joins idempotently; absent read/write permission, unrelated directories, wrong repo identity, and incompatible schema are diagnosed without destructive changes.
3. A blog saved in member A’s hub becomes readable/resumable by member B after sync, including portable outline/draft/history, source/voice pins, notes, checkpoint, and review status. Full library ingestion is unnecessary.
4. Sources, voices, user rules/context, and reviews share through the same revision model. User-defined scope and current-request precedence are honored.
5. Two member clones adding different records converge. Two edits of the same baseline preserve both and expose a semantic conflict; resolution retains both parents.
6. Offline/interrupted saves remain queued and durable. Retries and ambiguous push/creation results do not duplicate artifacts or silently lose work.
7. Protected branches produce a pending contribution, never a false shared-success result or changed protection.
8. The instruction repo, executable updates, and hub data remain separate. A hub file cannot install or execute remote code.
9. Real multi-member GitHub and harness pilots are distinguished from local/mocked tests. No global install, live repo creation, invites, or Google edits occur merely while designing/testing fixtures.

## Provider references

Creation can target an account or organization where the actor has sufficient permission; organization policy may restrict creation. [GitHub repo creation](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository).

The GitHub CLI supports private repo creation and local cloning; use explicit owner/name rather than the authenticated-user default. [GitHub CLI repo create](https://cli.github.com/manual/gh_repo_create).

Write permission supports pushing; access administration is a separate role capability. [GitHub organization repo roles](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization).

Git rejects non-fast-forward pushes by default to prevent history loss. The proposed retry/append protocol builds on that behavior and never force-pushes. [Git push](https://git-scm.com/docs/git-push).

## Implementation boundary

Local runtime/guidance implementation is complete. See [Team Hub usage](../../team-hub.md) for shipped behavior and verification. The real GitHub/member and harness pilot remains pending an explicit target; Google Docs provider operations remain separately planned.
