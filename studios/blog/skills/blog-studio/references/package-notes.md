# Package and provenance

Blog Studio is self-contained: its entry point routes to twenty modules:
nine adapted from BlogForge, five from the original shortlist, and six authored
Google workflows using the current harness provider.
The collected [library notes](library-notes.md) document the original sources
and their omitted Claude-specific runtimes. Their descriptions remain source
references; Blog Studio controls conversation, scope, and continuity.

[sources.lock.json](../sources.lock.json) records the unchanged upstream files.
[blogforge.lock.json](../blogforge.lock.json) records the inspected BlogForge
revision and seven copied instruction assets. Adapted module text is authored
for this package. The writing, editing, strategy, and copywriting modules are
concise working guides with optional upstream depth; workspace operations load
through focused references. Routine work does not require those four originals.
BlogForge servers, accounts, APIs, and model providers are not
required. Use the host's model and actual available tools.

Local helper scripts require Python 3.11+ and the standard library. The guided
page runner starts a signed-in Codex or Claude CLI for bounded writing jobs;
public research is allowed only when selected. Website imports fetch selected
public pages. Other writing and connected-service operations use the host’s
available capabilities. Workspaces live outside the installed skill.

The browser bundles Training Studio’s MIT-licensed page stylesheet and safe DOM
Markdown renderer unchanged. [The UI provenance record](../assets/management/training-studio-ui.json)
pins their source revision and hashes; [the upstream license](../assets/management/training-studio-LICENSE.txt)
is included. Blog modes, controller and compatibility styles are authored here.

Run `python3 scripts/validate_package.py` for source integrity, routing, and
local-link validation. It checks all twenty modules and their conditional routes.
The installer copies this whole folder, entry file, references and helpers
together, and records a manifest of file hashes that `readiness` verifies. For a
manual install, copy the complete folder into a skill root, or load `SKILL.md`
by absolute path. No implicit-only or explicit-only invocation restriction is
introduced. Copying a package into a skill root requires ordinary filesystem
permissions; do not work around host restrictions.

## Privacy boundary

Apply [data boundaries](privacy.md) when borrowing upstream techniques.
Original service examples are archival instructions, not installed integrations
or authorization to send private content elsewhere.

## Research

Research runs on the `harness-research` companion skill, the same runtime and
evidence contract Training Studio and Presentation Studio use, pinned in
the installer's `companions.json`. The
[Blog Studio module](modules/blog-deep-research.md) adds the article's research
policy, attached references and exact draft claims around it. harness-research
credits the MIT-licensed Deep Research skills it grew from in its own NOTICE.
Load only this conditional module for topic research or factual evidence gaps.
