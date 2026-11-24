# Human-readable Team Hub library

Approved 2026-10-02: generate a GitHub homepage index and author/title folders
with rendered blogs, outlines, selected context links, and revision history.

- Immutable memory records remain canonical; generated files never drive writes.
- Derive author from explicit article metadata or its pinned voice; otherwise
  group under Unassigned. The last editor never becomes the author implicitly.
- Regenerate views in the same commit as shared saves, after concurrency rebase.
  Pending review views stay on the contribution branch until merged.
- Preserve custom homepage prose outside a marked generated block. Detect edits
  to generated files and stop before replacing them. Rename/retire removes only
  generated paths; canonical history and IDs remain intact.
- Migrate old hubs with the next successful save/sync. Raise minimum runtime to
  1.3.0 so older clients reject the new layout instead of misinterpreting it.
- Validate deterministic output, collision handling, hostile metadata, history,
  rename/removal, two-clone conflict/retry, review branches, and upgrade behavior.
  Run the complete relevant suite in Tart. Do not publish or update a real hub
  as part of implementation.

Completed locally. See [validation](../../team-hub-library-validation.md): 129 tests passed in Tart. Real hubs and installed user skills were not changed.
