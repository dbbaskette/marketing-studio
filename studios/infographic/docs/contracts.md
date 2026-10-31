# Infographic Studio saved contracts, schema 1

`runner/contracts.py` and `runner/validation.py` own the native contract. They import
only the standard library and one another. Unknown schema versions are refused;
the foundations do not convert another studio's content or saved work.

## Record identities and limits

A project records the full product name, stable ID, workspace owner, integer
revision, brief, captured sources, facts, stories, selected story, brand, scene,
assets, image briefs, attempts, checks, approval, and exports. IDs are bounded
ASCII identifiers, and SHA-256 identities are lowercase hex. Canonical JSON uses
sorted keys, UTF-8, and finite numbers; unsupported values, credentials/session-key
fields, excessive nesting, and records larger than 2 MB are refused.

Sources are at most 16 MB; raster assets are at most 32 MB, 20,000 pixels per
edge, and 40 million pixels overall. Source/evidence locations refer to captured text character offsets, with
explicit original-byte sizes and digests. File references must be relative and
cannot contain parent traversal, absolute paths, URL schemes, or alternate path
separators. Workspace reads open each path component without following links,
check regular-file type and size before reading, and verify saved hashes.

Dates, units, denominators, conditions, and source qualifications belong with
facts. Numeric values require explicit units. Derived facts retain an operator
and stable operand IDs; sums/differences require matching units, ratios and
percentage changes state their derived units, zero denominators are refused,
and calculation cycles cannot validate. Actual quote/value interpretation is
checked by the later source-evidence stage, not inferred by this schema validator.

## Story, scene, and image brief

A brief records title, audience, purpose, direction, preset, required ideas,
locked wording, and exclusions. Story blocks refer to known facts and required
ideas; omissions are explicit. A selected story must exist. Scene dimensions use
points for A4/Letter and pixels for digital, exactly matching the selected preset.
Every element has an ID, type, positive bounds inside the page, and applicable
fact/asset references. Text retains explicit wording, font, and type size.

Image briefs pin story, scene, input basis, exact provider-ready prompt, canvas,
reading order, visual style, exclusions, acceptance, composition regions, objects
and counts, references, facts, and compositor-owned text. Region ownership separates
image-generated artwork from exact labels/charts the compositor controls. Regions
use normalized bounds. The later image-brief authoring stage fills and semantically
checks the complete detailed art direction; a generic prompt is insufficient.

## Revision basis and invalidation

The input basis hashes brief, sources, facts, stories, selection, brand, scene,
and assets. Worker results carry the exact basis, expected revision, owner, and
attempt ID. `can_land` permits only a current, running, owned attempt. Cancelled,
unknown, outdated, and foreign results cannot become current work.

`advance` rejects stale edits and owner mismatches, increments a changed revision,
clears approval, and conservatively invalidates dependent stories/scenes/briefs/
attempts/checks. A no-op preserves the revision. A brief change to the title alone is a
rename (`renamed`): the next revision clears nothing, and because the page's pixels and
checks are unchanged its checks, latest visual review and approval move to it with the
new basis, each recording `carried` with the revision the person reviewed or approved.
The earlier revision's approved exports stay as they were. More granular unaffected-element
reuse and compare/restore belong to the later history issue; no foundation method
silently claims that dependency-aware editing is complete.

## Provider attempts and approvals

`runner/images/base.py` defines the shared readiness/generate/edit/status/cancel
protocol. `validate_image_result` checks schema, provider, operation, owned attempt,
normalized outcome, request identity, returned asset metadata, inspection capability,
and reported-or-unknown usage. A completed generation/edit must return saved assets;
an unknown timeout cannot be represented as success. Cost includes a currency or
both remain unknown. This protocol performs no network operation.

Image attempts name Codex or Gemini and a saved image brief. States are queued,
running, complete, failed, cancelled, or unknown. A timeout with an uncertain remote
outcome remains unknown instead of triggering another billable request. Reported
cost is nonnegative or explicitly unknown. Reference and returned assets have
stable file identities. The production adapter/scheduler, not this contract,
executes jobs and enforces cancellation and the shared repair budget.

Checks bind scene and complete input basis. Final approval requires the current
owner/revision/scene/basis, coverage/factual/visual/layout/brand-accessibility checks,
no failed/incomplete blocking check, and no required omissions. A provider response
is not a visual check. Human review of an unavailable image-inspection capability
must be recorded by the future review flow, not invented by a worker.

Approval and provider/check records are not writable through the foundation
browser API. Only draft creation and full-brief edits are exposed. Native schema
validation is necessary but does not grant authorization to approve or publish.

Exports retain revision, input basis, and immutable file hashes. Old exports may
remain after a new revision, but they are never the new revision's approval.

## Persistence and recovery

An explicit local setup creates an isolated Git repository without identity,
hooks, templates, accounts, fetches, pushes, or commits. Existing populated folders
are refused unless an explicit setup identifies a valid native workspace marker
for recovery. Configured workspaces cannot be moved by later defaults or setup.
The foundation reads the existing shared settings authority; it writes no shared
preferences and never creates a parallel shared settings file.

Every write holds the native workspace lock. A project saves immutable canonical
revision files named by revision and content hash; an atomically replaced pointer
selects the current file. A crash after writing a version but before updating the
pointer leaves the last good revision current. Retrying a different edit at that
revision does not overwrite the orphaned immutable file. Reads verify pointer,
hash, schema, project identity, and workspace ownership.

History restore, source intake, provider execution, check execution, and user
approval are intentionally later capabilities. The foundation's informational
page and status report that distinction directly.
