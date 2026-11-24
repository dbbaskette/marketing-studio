# Week 7: local recovery and direct resume

Scope #324/#321. Persist safe build-stage receipts separately from immutable
Infographic Studio page revisions. A failed composition, font check, artwork
placement, preview or export identifies completed work and the next explicit
local retry. A changed page makes an earlier retry stale. Never replay an
uncertain image request; use its existing recovery protocol. Private diagnostics
record only exception type and stack basenames, not raw exception values or
prompts. The API returns a safe receipt; the page replaces an outdated build
dialog, and reload shows the same recovery card.

Each studio writes a compact metadata sidecar under its ignored work/ folder when
it saves work. Scratch validators never publish it; checked Training Studio publication
updates it only after committing the native result. Derived metadata is excluded
from checked content/proposal identities. Marketing
Studio reads only these bounded sidecars, at most 100 folders and 12 rows per
studio, without importing engines, initializing workspaces or contacting
providers. Show saved Needs you / In progress / Recent work above launch cards;
activity is explicitly last-saved state, not a claim that a process is alive.
Old work uses a bounded current-record fallback (128 KB per metadata file, no content/history traversal); oversized or unreadable records are omitted. New saves write compact sidecars. Missing workspaces and limited
results are described honestly. The summary contains no document text, absolute
paths, tokens or private links.

Resume validates an existing owned summary before launching, retains the native
session fragment, and resolves a relative work ID through the native listing.
The exact pending decision opens without carrying approval. Test safety and
bounds with disposable data, 5,000 synthetic folders, native authenticated APIs,
real browser recovery, keyboard/layout checks and the complete relevant gate.

The earlier end-to-end audit encountered a Git index-lock collision while polling.
Presentation Studio and Training Studio status reads now disable Git's optional
index refresh. Write commands retain their required locks and saved environment.
Targeted transport tests cover both cases; the full native gates cover existing
repository ownership, sync and commit behavior.

Impact previews read no selected capture bytes before an approved research case
exists or while work runs. Resting views reuse a small 30-second cache keyed by
current case, record/source metadata and questions. Explicit confirmation always
rehashes actual source bytes and invalidates the cache before accepting a scope.
Native tests verify two polls read once and confirmation reads again with zero
assistant work. Unmanaged external edits can remain visually cached for at most
30 seconds, but cannot pass confirmation with an outdated expected identity.


## Completion evidence

Merged in [PR #333](https://github.com/dbbaskette/marketing-studio/pull/333), squash
`5f0b05d8e9cf27a0c739f06f6eba7cd229403d0a`. Its tree exactly matches the final
complete Tart gate at `4a6ba2b555810d1946e3ac53c0ff2e3dc1539e02`:
`3dba8a81604362cb8a883b4fa1a1ae93c8bf165d`. Shared 975, Infographic Studio 258,
Blog Studio 1,876, Presentation Studio 2,183 and Training Studio 3,177 tests,
both home/recovery browsers, every package check and standalone/shared setup,
authenticated launch/reuse/cleanup, Hub 41-step and CLI 39-command acceptance
passed. Two explicit PDF-reader acceptance skips retain separately passing Week 4
synthetic-PDF evidence. Environment: macOS 27.0, Python 3.13.15, Node 22.23.2.
The disposable VM was deleted; GitGuardian passed before merge. No providers ran.

The final fresh gate includes corrections found during integration: derived home
metadata stays under ignored work folders, scratch validators cannot publish it,
and checked content/proposal identities omit it. A concurrent edit during a failed
render leaves recovery bound to the revision that failed. The regression tests
and all native compatibility flows passed after those corrections.
