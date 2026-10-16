# Team Hub library validation — October 2, 2026

Implemented in the unpublished **1.3.0** candidate, on top of the usability work.
Canonical memory stays under stable IDs; the repo homepage and `blogs/<author>/<title>/`
are generated browsing views. No real Team Hub was modified during implementation.

## Verification

**129 tests passed in Tart with Python 3.13.16, in 97.721 seconds.** This includes
all existing installer, guidance, Google checkpoint, privacy, local writing, and
shared-workspace tests, plus ten new library tests covering:

- Empty/new hub and legacy hub upgrade; idempotent sync without synthetic memory.
- Rendered manuscript/outline, selected source links, readable history, and valid
  relative navigation links; unrelated notes/source bodies are not copied.
- Explicit author, pinned voice fallback, and Unassigned; editor identity does not
  silently become article authorship.
- Duplicate/sluggified titles, long shared ID prefixes, and names that collide with
  generated suffixes; unsafe metadata does not escape paths or Markdown tables.
- Renaming and changing author metadata while preserving immutable history.
- Retiring an article removes only its generated current paths.
- Two-clone competing changes show unresolved heads without selecting a winner.
- Generated-page edits block overwrite and retain queued work; custom homepage text
  outside the generated section is preserved.
- Review-required hub upgrades and saves remain on their contribution branch until
  merge, including upgrades with no pending memory operations.
- Older runtimes reject the upgraded minimum-runtime manifest with an upgrade message.

The first targeted run found that `git update-index --force-remove` needed a working
checkout. The hub uses a bare repository and a private index. Removal now uses
index-info deletion records, limited to generated `blogs/` paths; rename, retirement,
and legacy-upgrade cases then passed.

Both distributions were rebuilt. Skill/package validators, source provenance hashes,
guidance inventory, shell syntax, and patch whitespace were checked. A fictional
local preview demonstrates the homepage and two author folders; it is not a public
or private GitHub deployment.

## Rollout

Install the 1.3.0 runtime on contributing clients before upgrading a team hub.
New hubs include the library. Existing hubs generate it on their next authorized
save or explicit `sync`; joining/refreshing remains read-only. Protected-branch
policies still govern when the library becomes visible on main.

Generated pages are for browsing. Direct GitHub edits must be preserved/imported
and the generated files restored before sync resumes. Canonical IDs and historical
content survive author/title changes, but readable folder bookmarks may change.
No direct GitHub editing importer, real second-member pilot, Google connector test,
or deployment to the user's existing hub is claimed here.
