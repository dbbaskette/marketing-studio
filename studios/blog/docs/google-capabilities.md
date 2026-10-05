# Google connection and team review contract

The supported writing environments are Codex and Claude Code. Both receive the
same installed runtime. Google availability is discovered in the actual session;
an installed Workspace skill or a working connection elsewhere is not evidence
of this session's tools or file access.

For local CLI use, the implemented gcloud adapter uses an existing user login.
No custom OAuth client, Cloud project, billing setup or gws credentials are
required by Blog Studio. If the session already exposes a suitable connector,
use its actual operations and current preservation instructions. Google remains
optional for core installation and writing.

## Team choices versus local setup

| Record | Where it belongs | How it is selected |
| --- | --- | --- |
| Intended harnesses and preferred connection | Ordinary selected team context in the private Hub | User chooses Codex, Claude Code or both and the connection |
| Review folder and optional native template | Ordinary selected team context in the private Hub | User provides links; unselected choices remain unselected |
| Intended review audience | Ordinary selected team context in the private Hub | User states the audience; this does not create a grant |
| Account, exposed tools, access and capability observations | Private local setup record | Inspect this harness and the selected document |
| Disposable pilot Doc/folder/template | Private local pilot manifest | User explicitly selects the destination and permitted test operations |
| Linked working Doc, tabs and transfer baseline | Selected article and its private Hub history | Actual provider readback and verified checkpoint |

Ask only for a choice needed by the current operation. Do not require team
onboarding for an ordinary draft or invent a preferred destination. An existing
linked article continues in its original Doc unless the author requests a new
copy. Before folder placement, inspect its actual direct/inherited audience;
team preferences do not authorize permission changes, notifications or invitations.

No account or pilot destination is selected by this repository. The earlier
fictional-provider pilot's destination identifiers remain in its private local
manifest. Reuse them only within their explicit authorization; do not copy them
into another team's setup.

## Implemented routes and acceptance evidence

“Implemented” describes code and conditional guidance, not account access.
The Codex observations below apply only to the authorized disposable fixtures
in the [dated acceptance record](issue-validation-2026-10-03.md).

| Operation | Local gcloud route | Connected Codex evidence | Remaining live boundary |
| --- | --- | --- | --- |
| Source read, accepted text, nested tabs | Native Docs read with suggestions excluded | Selected-tab intake and native multi-tab reads verified | Rediscover access/scope in each participant's harness |
| New editing copy | Drive HTML/DOCX/text import with audience check and recovery receipt | Native handoff, heading/link readback verified | No template fidelity implied by plain import |
| Existing-document edits | Native Docs update with required revision and readback | Stale revision rejected; three-way conflict and resolved return verified | Current file permission and author decisions remain necessary |
| Native template copy | Base adapter does not implement copying | Complete native multi-tab template, styles and date control retained | Use a capable connector; no unsupported control mutation promised |
| Pending suggestions and anchored review | Separate configured review helper; native readback required | Pending suggestion and visible explanatory anchor verified through gcloud | Connector has no top-level writeMode; no general anchor/parity assumption |
| Ordinary review comments | Review helper with current quoted context and readback | Document-level and native anchored outcomes verified separately | Cannot infer inline location from a Drive API response |
| PDF/Word/Markdown export | Requested Drive export; snapshot/version checks; local inspection | PDF visual QA and Word prose/heading inspection passed | Other layouts/formats and participants need their own affected checks |
| Permissions/audience read | Paginated Drive permissions and metadata | Owner-only disposable folder/document readback verified | Group membership and later grants are not frozen |
| Change sharing | Requires a connector with exact grant and permission readback | Schema and local receipt fixtures only | Actual recipient/permission test remains #14; silent sharing unsupported by inspected action |

Claude receives these same local helpers, but its Google tool discovery and
participating-user behavior have not been validated by the Codex tests. Missing
or unobserved capabilities stay unavailable or unknown with a local fallback.

## Compact capability record

The existing `studio.py --root WORKSPACE google capabilities --file FILE` command
stores a bounded, local-only observation. Schema 1 requires `harness` (`codex` or
`claude`), timezone-aware `checked_at`, and a `capabilities` map. Each entry has
`status` (`unknown`, `unavailable`, `exposed`, `verified`) and an actual `tool` name
for exposed/verified operations. Missing entries mean unknown. Supported keys
are defined by `google_workflow.py`'s `CAPABILITIES`; raw provider responses,
account details and credentials are rejected.

Inspect schemas to record exposed tools without making a live mutation.
Verified requires an authorized operation and readback; do not mark an entire
transport verified from login alone. Refresh observations when the session or
access changes. The helper writes `.google-capabilities.json` locally and does
not sync it to the Hub; save separate observations when evaluating two harnesses.
The command checks record consistency, not the truth of a provider operation.

## Identity, scope and preservation

The [adapter contract](../skills/blog-studio/references/google/adapter.md) and
[checkpoint contract](../skills/blog-studio/references/google/checkpoints.md)
define canonical Doc identity/URL, selected tab IDs, actual revision or disclosed
fingerprint fallback, direction/time, accepted-text hash and verification.
Provider revisions guard existing-document writes; fingerprints alone do not.
Before return, compare the saved baseline with both current copies. Preserve
originals, formatted DOCX/native evidence, Markdown history and article pins.
Suggestions/comments remain separate and are never implicitly accepted.

Credentials stay in the connector or gcloud store. Share only selected article
content; sources, interviews, rules and voices are not automatic attachments.
Sharing, export and editorial readiness remain separate from publication.
