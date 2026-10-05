# Blog-owned editorial files and reusable memory

The user approved the blog-folder layout and requested implementation in Blog
Studio and the existing private Tanzu Marketing Hub. No additional spec approval
is needed. Implement in an isolated worktree; preserve unrelated CI edits.

## Outcome

- `blogs/<author>/<title>/` exposes the draft, immutable original, outlines,
  reviews, selected sources, companions, import attachments, and readable history.
- `memory/` exposes reusable rules, voices, context, notes, and decisions. It
  does not contain article drafts or article review records.
- `.blog-studio/items/` holds immutable synchronization records. All existing
  record and artifact bytes, identities, parents, and dependency pins survive.
- Runtime 1.13.0 reads old hubs and upgrades them during authorized sync. Old
  clients cannot write the new schema. Manually edited views stop migration.

## Implementation and verification

1. Centralize revision paths and immutable-content comparison. Support both
   storage schemas, remap queued payloads without changing their operation IDs,
   and preserve competing contribution branches. One owner: this chat.
2. Extend generated blog folders and reusable-memory views. Preserve selected
   scope, binary snapshots, review coverage/status, conflicts, renames, and
   deterministic paths. Verify all generated local links and byte equality.
3. Update guidance, user documentation, installer manifest, and both packages.
   Run focused migration/sync tests, then the existing full local CI entry point
   and package/installer checks. Retain logs and tested source state.
4. Install through the trusted local installer, sync the selected private hub,
   and verify the remote tree, preserved records, reviews, and repeat-sync
   idempotence. Keep originals in Git history; do not force-push.

## Review focus

Check refresh immutability across path relocation, outbox retries from old
layouts, read-only/review branches, competing edits, malformed paths, generated
view edits, binary limits, source pin scope, and old-client version rejection.
No Google transfers, public release, credential changes, or CI service changes.
