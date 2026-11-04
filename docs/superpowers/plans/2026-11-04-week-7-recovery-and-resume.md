# Week 7: local recovery and direct resume

Scope #324/#321. Persist safe build-stage receipts separately from immutable
Infographic Studio page revisions. A failed composition, font check, artwork
placement, preview or export identifies completed work and the next explicit
local retry. A changed page makes an earlier retry stale. Never replay an
uncertain image request; use its existing recovery protocol. Private diagnostics
record only exception type and stack basenames, not raw exception values or
prompts. The API returns a safe receipt; the page replaces an outdated build
dialog, and reload shows the same recovery card.

Each studio writes a compact metadata sidecar when it saves work. Marketing
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
