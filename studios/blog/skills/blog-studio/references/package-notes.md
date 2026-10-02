# Package and provenance

Blog Studio is self-contained: its entry point routes to fourteen modules,
nine adapted from BlogForge and five retained from the original shortlist.
The collected [library notes](library-notes.md) document the original sources
and their omitted Claude-specific runtimes. Their descriptions remain source
references; Blog Studio controls conversation, scope, and continuity.

[sources.lock.json](../sources.lock.json) records the unchanged upstream files.
[blogforge.lock.json](../blogforge.lock.json) records the inspected BlogForge
revision and seven copied instruction assets. Adapted module text is authored
for this package; BlogForge servers, accounts, APIs, and model providers are not
required. Use the host's model and actual available tools.

Local helper scripts require Python 3.10+ and the standard library. They do not
fetch links, extract binary documents, write prose with a model, or call paid
services. The agent performs those tasks using available host capabilities and
records the results. Workspaces live outside the installed skill.

Run `python3 scripts/validate_package.py` for source integrity, routing, and
local-link validation. It checks the five source modules plus nine new ones.
The full offline package includes that validator. Repository snapshots retain
provenance and references; use the installed runtime for executable helpers and
the managed installer for runtime checks. For offline/manual discovery, install
the complete folder, or load `SKILL.md` by absolute path immediately. No implicit-only or explicit-only invocation restriction is
introduced. Copying a package into a skill root requires ordinary filesystem
permissions; do not work around host restrictions.

## Privacy boundary

Apply [data boundaries](privacy.md) when borrowing upstream techniques.
Original service examples are archival instructions, not installed integrations
or authorization to send private content elsewhere.
