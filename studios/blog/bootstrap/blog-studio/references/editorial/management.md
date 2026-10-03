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
