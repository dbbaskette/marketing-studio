# Local editorial desk

On “Open editorial desk”, use the current installed interpreter/runtime:
`<python> <runtime>/studio.py --root <workspace> manage`.
The helper runs until stopped and returns a local URL with a per-run session
fragment. Open that exact URL in the available browser. Keep the helper process
running; stop only this desk process when the author asks. Do not open a new
workspace or join another Hub implicitly.

The desk browses local/selected-Hub blogs, cached Google links, attention,
references, uploads and scoped shared memory. Shared-only blogs can be resumed
without overwriting local edits. Uploads preserve originals; PDF extraction is
pending, and starting an editable blog is a separate choice. Curation and memory
changes retain Git revisions. The server verifies current GitHub write access
for Hub mutations. Everyone with write access has the same controls; GitHub
admins manage membership. Offline/unverified Hub access can prevent UI writes;
the ordinary harness still preserves local work and queues sharing.

The desk binds only to 127.0.0.1 and uses a session token. It is not a hosted team
website. Ordinary GitHub Pages is public even from private repos; do not deploy
private content there. The private Hub's generated board/catalog is the shared
browsing view. Google content/feedback refresh stays explicit in chat; the desk
never sends posts or changes Google sharing.

Desk lists ignore superseded view/filter/page requests and show loading while
pagination is disabled. Curation forms bind the inspected source state; a changed
local record or shared head refuses the save. Keep the proposal, use “Reload and
compare,” then explicitly choose the latest values or retain the proposal before
saving again. Unshared local edits need comparison in chat; never overwrite them
by resubmitting a shared form.

Runtime 1.12.2 adds phone/tablet stacked results and focused details. Article and
finding dialogs show bounded saved previews, review freshness, explicit stop
points, and copyable article-specific requests. Use that selected identity when
the author returns to chat; inspect current state before editing. A saved shared
review is not proof of local freshness, and a stale ready/published decision must
not be renewed automatically. Metadata, reviews and evidence/history remain
secondary disclosures. Inbox search filters before pagination.

The access panel distinguishes local-only, verified write, read-only, expired
sign-in and unavailable verification. Refresh uses existing read/identity/privacy
checks; actual writes still reverify contribution permission. Decisions,
collections, candidate lessons and conflicted memories have read-only details
with focused continuation. Never convert them via the generic note editor.
An access observation is informational, not a reusable write authorization.

Runtime 1.14 adds Reference library → Import old blogs. Folder and JSON-export
pickers stage only selected files locally (500 files / 10 MiB total). Website,
feed, sitemap and explicit links use approved HTTPS post scopes. Preview precedes
explicit 25-post import batches; saved checkpoints survive desk restarts, retries
retain identity, and results distinguish extraction failures and Hub sharing.
Use Refresh an existing collection to keep the same historical identities.
Larger local folders still use the focused library commands in chat.

Runtime 1.14.1 lists all preview candidates with checkboxes, labels and URLs.
Nothing is selected automatically. Only checked posts are fetched; remaining
checks persist across batches and restarts after the first import. Retry acts
only on checked failed posts. Labels are source data, not proof a link is a blog.
