# Remaining Marketing Studio backlog

User contract: review every remaining open issue, spec and implement needed work,
and close work that is already resolved or unnecessary. Continue the existing
verified pull-request/merge cadence. Baseline: `e308d3a8`.

## Disposition and acceptance

| Issue | Current evidence | Required outcome |
| --- | --- | --- |
| #308 | CLI reuse bypassed by --no-open and --lan | Ask the running home through its private same-user control socket, retain terminal-only secret disclosure, reuse existing phone access, refuse unavailable phone access without starting another home |
| #309 | Test observes a shell before exec/session identity stabilizes | Wait for the exact process group, assistant command and nonempty start identity; retain wrong-start refusal and orphan survival; 50 isolated repetitions and full shared Tart gate |
| #304 | Project totals still hard-stop; #297 is merged | New tasks default to warning, with explicit hard-stop setting and per-project override; old saved hard-stop tasks retain their policy until an explicit change; fixed positive job caps and existing time/round limits remain; warning is durable, once per crossing, visible on desk/home/Activity |
| #310 | Brands implementation exists on an older unmerged branch | Adapt selected implementation to current main; brand.brands/brand_data is the sole destination authority, no team-hub brands fallback or stale environment override; staged review, one-brand writes/commit, explicit push, safe cancellation/concurrency and real browser coverage |
| #152 | Scoped adapter and offline corrections merged in #183/#186/#231 | Verify current adapter contracts; preserve actual signed-in generate/reference-edit acceptance as an explicit release gate |
| #223 | Workbench merged in #231, later UI/recovery work also merged | Reuse current deterministic UI/render evidence; preserve actual-artwork owner/visual/accessibility acceptance |
| #224 | Delivery workflow merged; final release gate remains | Reconcile documentation/platform/evidence and consolidate remaining live/owner gates without declaring them passed |

Live providers, keys, Google writes, publication of release assets and real-user
upgrades are separate authority. Prepare concrete synthetic acceptance cases and
operator steps; do not turn fixtures into illustration-quality sign-off. If #152
and #223 no longer need separate engineering tracking, close them as consolidated
only after moving every unmet criterion into #224. Keep the release gate open.

## Interfaces and compatibility

Launcher reuse uses existing `state`/`open` messages rather than another IPC or
secret-bearing stdout channel. The CLI's Report controls terminal/JSON output.
Process tests wait on observed readiness rather than sleeps; wrong process identity
must still refuse signalling.

Spending policy is warn or hard-stop. Shared settings retain their adjacent lock,
unrelated values and stale-form conflict checks. New projects pin their choice;
missing saved policy preserves old hard-stop semantics. An existing stopped task
keeps Carry on and can explicitly choose warning in Change settings. Continue
never silently lifts a hard cap. Unknown dollar usage stays unknown. Warn-mode
jobs have documented finite caps independent of the remaining project allowance.

Brands work runs in Marketing Studio's own scratch directories until Save. The
configured brands repository is independent of shared team storage. Each save
checks its original basis and commits only that brand; unrelated dirty/staged
files must never be included. Push requires a distinct explicit action and must
not send unrelated pending work silently. Read-only listing never initializes,
fetches, installs or runs providers. Existing shared UI and native studio worker
confinement remain intact.

## Verification

One owner runs focused checks at each coherent milestone and the complete relevant
Tart gate before that cohort merges. Use disposable roots, Git identities, local
repositories, fake workers and browsers. Reuse passing unchanged-tree evidence;
repeat affected checks after fixes. State transitions require native matrix rows.
