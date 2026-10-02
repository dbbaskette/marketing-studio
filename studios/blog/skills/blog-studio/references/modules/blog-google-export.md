# Export or explicitly share a Google Doc

**Input:** selected native Doc and requested format or exact audience/access.
**Output:** inspected PDF/Word artifact, or verified requested permissions.
Follow [adapter](../google/adapter.md), [privacy](../privacy.md), and the active
Google Drive skill. Export does not imply sharing or public publishing.

## PDF or Word

Read metadata and selected accepted text/structure first. Confirm native MIME
type and capture revision/fingerprint. Export only the requested format through
the supported provider action. A whole-document export can include other tabs;
check scope before exporting and offer a selected-content local artifact if the
provider cannot export only authorized tabs. Never include private source
appendices, interview notes, voices or rules as incidental export content.

Use authenticated file references/materialized files returned by the provider,
not bearer URLs, inline base64 or a newly public link. Handle provider size limits
and missing format support without an unrelated upload service. Read the Doc
again after export; if revision/content changed, the selected version is not
verified. Reconcile and re-export, or disclose the race. Inspect the actual PDF
or Word artifact with available PDF/document tools: title, selected content,
headings, tables, links and omissions, plus rendered layout when material. A
successful export call or valid filename is not artifact verification. If tools
cannot inspect it, deliver it as unverified and say what remains unchecked.

Optional receipt: operation `export`; requested/observed objects contain `format`
(pdf/docx), `content_sha256` and `inspected`. Observed also includes actual
`artifact_sha256`. Set verified only after inspecting the actual file and matching
the selected document version. Preserve local Markdown alongside requested files
when useful; leave auth references and transient local paths out of shared memory.

## Requested sharing

Resolve recipient emails or exact company domain, reader/commenter/writer access,
and notification intent from the user's request. No implicit team-wide permission,
public link or ownership transfer. Inspect current direct/inherited permissions;
do not disturb unrelated grants. A chosen folder is not permission to broaden
its audience. Confirm only missing consequential intent, not already-authorized
mechanics. A user's request to share does not authorize separate email/chat.

Inspect the current sharing tool's notification semantics. If it cannot honor
requested silent sharing (the inspected Codex action has no notification control),
stop before sharing and offer a supported explicit choice. Do not claim silence,
add a notification tool, or assume the default is safe. Apply only the selected
grant, then read back permissions. Report per-recipient partial failures and
avoid duplicate retries. Missing permission readback means unverified, not done.

Optional [receipt](../google/checkpoints.md): operation `sharing`; requested and
observed lists contain `{type, audience, role, notify}`. Type is user/domain,
role reader/commenter/writer; notify records the actually supported/observed
notification behavior, never a guessed silent default. Store only requested
grants, not the file's entire access list. Access changes are separate from
publication approval and the article's editorial checks.
