# Publication package

Use the selected saved draft and ask only for missing consequential choices:
channels, intended audience, or actual publication URL. Reuse the existing
[repurposing module](../modules/blog-repurpose.md) and
[exports](../export.md) when requested. Prepare final copy, a summary, selected
social drafts, metadata and working/output links. Do not call external publishing
services or change document sharing.

Save `editorial package --id <id> --file <json>` with `channels`:
`[{"name":"LinkedIn","text":"prepared copy","manuscript_quotes":["exact supporting draft passage"],"max_characters":1000}]`, optional publication_url and notes.
The helper preserves `derived/publication-copy.md` and records its hash/path, working Doc link, lengths, missing URL,
and provenance in `derived/publication-package.json`. Use the requested platform's
verified limits, or explicitly supplied limits; absent limits remain unknown.
Supporting excerpts establish provenance, not semantic validation. Review every
channel draft for unsupported factual additions and report those findings.

`editorial assets --id <id>` detects stale inputs or changed companions. Export
using available tools, reopen/verify files, then record their actual paths and
limitations in the package notes. Preparing a package does not approve release.
