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
Old work gains metadata on its next native save. Missing workspaces and limited
results are described honestly. The summary contains no document text, absolute
paths, tokens or private links.

Resume validates an existing owned summary before launching, retains the native
session fragment, and resolves a relative work ID through the native listing.
The exact pending decision opens without carrying approval. Test safety and
bounds with disposable data, 5,000 synthetic folders, native authenticated APIs,
real browser recovery, keyboard/layout checks and the complete relevant gate.
