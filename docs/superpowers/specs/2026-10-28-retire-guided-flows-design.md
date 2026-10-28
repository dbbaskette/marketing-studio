# Piece 7: retire guided creation without stranding saved work

Date: 2026-10-28. Implements the final piece of the
[workflow audit](2026-10-26-workflow-audit.md). Pieces 1–6 are historical
authority, not work to repeat. The owner authorized implementation and merging
of the whole piece. There is no subsequent phase in this plan.

## Outcome and boundaries

New work started in conversation uses the same desk records as work started on
the page. Conversation can create, inspect and save work without opening a
browser or starting a nested assistant. A focused outline, interview, research
or passage request remains focused. Delivery, publication, paid work, installation,
design answers and approval are never inferred from permission to draft.

Saved work keeps working. Retirement means removing current gated creation and
irrelevant review-level controls; removing compatibility implementations requires
evidence for every supported format. An empty scan on one computer is not evidence
about other installations. Retained paths must be named honestly, with exit criteria.

## Global constraints

- Use full product names; Python 3.11 or newer, standard library only, no frontend build.
- Marketing Studio owns shared settings and launching; each Studio remains independently runnable.
- Use the existing studios-config file and adjacent lock; preserve unrelated values and conflicting-edit guards. Installation folders remain under one Save in Shared settings.
- Preserve original files, history, source and guidance pins, Google baselines, team ownership and readiness. No automatic migration, assistant installation or update, publishing or delivery.
- Only the person approves. Automatic continuation is recorded as continuation, never person approval; new or changed materials are not Ready.
- Follow docs/design/golden-gate.md: material only on navigation, toolbars and transient controls; opaque forms and reading surfaces, one primary action, a lede, 44px controls, no phone overflow.
- Person-facing text never says artifact, stale or lineage, and never exposes hashes.
- Verification uses disposable settings, workspaces, HOME, Git identities and processes. Never launch real Marketing Studio or Studio applications or provider, Google or image jobs. Fake scripted servers are allowed. Do not change workflow files.
- Public issues, PRs and docs contain no credentials, private content or machine-specific operational records.

## Current interfaces

Blog Studio has `desk.create(root, data)`, `desk.save(root, ident, seen,
part, text, source='save', session=None)`, `desk.reimport` and finished-only
`desk.open_run`. Its `studio.py` already imports chat edits into an existing desk,
but `blog_runner.py` still exposes gated `run create`. Desk starts omit saved
author and brand context, and Proofread omits some run-only checks.

Presentation Studio exposes `Engine.start(form, uploads=None)` and desk actions
through `runner/desk_actions.py`. Training Studio exposes `Engine.start(form)`,
`draft_card`, `draft_save` and finished-only `open_on_desk`. Both starts schedule
workers, so they cannot simply be called by conversation helpers. Training
Studio's existing `training.py desk` means serve the page and keeps that meaning.

Both `runner/studio.py` entry points expose `saved-work`, but their engines skip
unreadable records. `studio_core.saved_work.report(ids, found)` currently infers
unused from empty lists. Blog Studio has no equivalent safe scanner, and its
catalog is unsuitable because it can expire deleted work.

## Complete read-only inventory

Extend the existing report with `schema: 2`, `scope` (product, roots and
`local_only: true`), `complete`, and `issues`. Each path retains `id`, `about`,
`needed_by`, and adds `status` (`needed`, `unknown`, `unused`) and `unknown_by`.
Add `gated-flow` to the existing categories. A known dependency takes precedence
over unknown, which takes precedence over unused. Any unresolved candidate or
enumeration error prevents a claim that an affected path is unused.

Inventory declared roots and registered candidates, including missing records,
malformed or unsupported records, symlinks excluded by readers, orphan records,
and recoverable deleted Blog Studio items. Report absence or inability to enumerate
instead of silently skipping it. Do not follow arbitrary links or inspect other
computers. Explicit folders that do not exist are issues. An unconfigured scope is
not a global empty-workspace certificate. Scanning creates no files, locks, cache,
settings or network traffic, and performs no expiry or repair.

The report states its limits: local declared roots only; it cannot certify unmounted
workspaces, other clones, other installations or recovery history. Output can contain
local paths for the person running it; publish only synthetic examples and aggregate
compatibility conclusions.

## Conversation on the desk

Add explicit command groups for create, inspect and checked save. Inputs use JSON
files or stdin, outputs JSON, with bounded validation and readable failures. The
existing page-serving commands retain their meaning. New helper commands operate
on the same domain functions and locks as page writes, not HTTP/session keys.

Creation records `flow: desk` and an explicit conversation execution mode. It
does not call runner wake/resume, launch an assistant, fetch guidance, install a
companion, publish or deliver. The current harness supplies the requested content
through checked submissions. Existing companion contracts still validate research
and drawings; conversation is not permission to fabricate either. Each submission
is bound to the input/version the harness read. Team guards, active-worker guards
and cross-process locking apply before mutation. A running page cannot pick up
conversation work and launch a duplicate job; handing execution to the runner is
an explicit action with known scope.

The concrete submission envelope is `{kind, target, expected_basis, payload}`.
Context returns pinned inputs, requested scope, validation requirements and a basis
for an absent target as well as an existing target. Submission supports initial
text/outline, existing-part edits, and companion-produced research/drawing results;
these are checked domain operations, never an arbitrary file-write API. A synthetic
conversation must reach usable materials without falling back to handwritten run
records or a nested assistant.

The deck engines currently use a thread-only RLock. Add a shared reentrant process
lock around competing mutations, scoped to the workspace Git directory for Git
operations (a private persistent `studios-write.lock`), with a product-data lock
when no repository exists. Acquire the thread lock before the process lock; nested
acquisitions in one thread reuse the same handle. Recheck state after acquisition.
All participating page, CLI, worker-settlement and synchronization writers follow
that order. Blog Studio retains its existing repository/workspace lock order.
Read-only inventory never acquires a writing lock. Exercise real two-process races.

Conversation execution ownership is checked before recovery cleanup (`_tidy`),
worker acquisition, wake, queued continuation and interrupted-work repair, not
only at start. Explicit handoff takes a current basis and requested scope before
atomically transferring execution; it never interprets a page visit as handoff.

Read and save expose existing text parts and slide operations, including History,
source checks and readiness invalidation. Training Studio drawing-bound word edits
continue to require the person's explicit Harness Slides design answers. The caller
may supply those answers only after the person gave them; no default answer is chosen.

## Blog Studio parity

Apply saved author and brand defaults to new desk work, preserving explicit choices
and existing source/voice pins. Feed the pinned brand to the same writing context
used for desk work. Keep tone and explicit voice behavior honest in guidance.
Add reader-facing editorial-note/source-ID checks and example carry-over checks
to Proofread. Add GEO to Finishing as an explicit requested proposal tool, with
preview/apply and the existing version/basis protections. Do not remove older Tools
until the replacement is reachable.

## Explicit unfinished migration

Blog Studio's first migration increment accepts a supported saved manuscript
(`DRAFT.md` or `ORIGINAL.md`) or a losslessly round-tripping Markdown outline with
at least two heading sections. Outline words become briefs and prose remains empty;
research, reviews and handoff remain historical, and unresolved publishing gaps
remain gaps. Brief-only starts, early research/angles without those materials,
list/unstructured outlines and older Team Hub contexts keep their saved-flow path.
Removing those compatibility paths requires supported lossless transforms for
their early material and ownership formats; this increment makes no claim that all
gated formats have been removed.

For Blog Studio, original `session.json` and `derived/blog-run.json` stay byte-for-byte
at their original paths through migration and later checked desk saves. A fixed
`desk/migration.json` holds the effective desk session and historical interpretation;
the draft registers last. A pending journal prevents workers, recovery cleanup and
repository replay from picking up partial metadata, including within recognized
output caches. Repeat the original `desk migrate --article ID --expected TOKEN`
after interruption to roll back only matching additive outputs and recheck/apply;
changed inputs then refuse safely. Altered or unreadable outputs/journals require
restoring the saved desk records, never deleting a marker to bypass exclusion.

Each Studio offers a read-only preview, then an apply bound to that preview. Show
what can be retained, what will be held or left incomplete, and any prerequisite
that prevents migration. No worker, source, team or file change may occur between
preview and apply unnoticed. Bind the token to relevant record/content versions,
worker state, ownership and dependencies; recheck under the write lock.

Migration is in place and additive: preserve original records and material bytes,
history, research/source pins, Google baselines and prior real approvals as history.
Do not mark a half-finished step complete to make a desk appear. Incomplete materials
remain incomplete or Draft; no new work is scheduled. Existing finished adoption
remains supported and idempotent. Missing/unsupported content gets an actionable
refusal with its original saved flow still available. Cancellation changes nothing.
Unfinished migration does not call the finished-adoption transform unchanged:
Training Studio's finished transform intentionally changes practice dependency
interpretation. Prepare a pure bounded write set, keep the original approvals and
input records intact, and store desk-specific interpretation separately. Assign
conversation execution so restart does not resume the older worker. Applying the
write set is recoverable across a failure between session and run record writes.
Partial-write failure must roll back the migration metadata without losing prior
files. Repeating an applied preview returns the same result or a safe changed-state
refusal, never a second copy.

## Retirement and compatibility evidence

After replacements work, remove current gated-create entry points and review-level
write controls/routes. Keep saved `review.level` and per-run policy/layout readers;
omitting a control must not reset its stored value. Retain labels and decisions on
older work. Update all three SKILL.md entry points and linked guidance to prefer
desk commands, with explicit focused scope and a clearly marked saved-work path.
Update package versions and guidance minimum_runtime together when commands change.

Move ordinary test starts to synthesis stand-ins and remove the production
`LEGACY_RESEARCH` test escape hatch. Legacy-format fixtures exercise saved readers
directly, without creating new unsupported work through public starts.

| Path | Removal condition | Retention until then |
| --- | --- | --- |
| Gated pipelines/screens | Every supported saved state can resume or explicitly migrate with no lost work | Saved-record-only dispatch, including unfinished and unreadable recovery |
| Research question queue | Supported unfinished queue records can continue through a proven replacement | Narrow saved-record compatibility and its regression fixtures |
| Review layout 1 | Its saved review signatures and approval semantics have a compatible reader | Existing saved review reader and screens |
| Cover sample | Old pinned contracts and local cover state have a supported continuation | Compatibility for saved contracts; no new unsupported-brand start |
| Old Harness Slides capability fallback | Explicit minimum/capability guard rejects unsupported tools before mutation, and saved formats still read | Format readers remain even if runtime probing branches can go |

Do not delete shared pipeline building blocks used by desk execution. Record actual
eligible deletions and retained paths in current compatibility documentation, not
as an assertion that the entire old pipeline disappeared.

## Verification and completion

Each independently mergeable increment has focused regression evidence, a fresh
task review and a fresh whole-PR review. Before every normal protected merge, fetch
origin, integrate latest origin/main, preserve parallel changes, rerun affected
checks, and verify the exact PR head/check state. No bypass merges.

Final verification freezes source for all relevant suites, management journeys,
package validators and desktop/phone journeys against fake servers. Tart is preferred
when available, never installed as part of verification. Native application launch
and live provider/Google interoperability are excluded by owner instruction; fake
tests cannot establish them. Close the tracking issue only after the authorized
scope is implemented and merged, with retained compatibility and limits stated.
