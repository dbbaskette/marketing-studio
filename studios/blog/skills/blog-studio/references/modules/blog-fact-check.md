# Factual support capability

**Input:** manuscript and selected readable factual references.
**Output:** exact claims classified supported, unsupported, or contradicted,
with the relevant source/passage and explanation.

Extract checkable claims, including assertions hidden inside hedged statements.
Do not treat hedging as a reason to skip an underlying factual claim. Separate
opinion and the author's own reported experience from externally checkable facts.
A reference supports only what it actually says; preserve population, date,
methodology, causality, and qualifiers. Contradiction takes priority over missing
support. A linked page or keyword match is not adequate evidence by itself.

Without readable references the evidence check is unavailable; list claims needing
sources if useful, but do not return a clean bill of health. Unsupported means
not established by selected evidence, not necessarily false. Outside verification
is a distinct operation requiring available research tools and permitted scope.

Save factual-support results through [workspace](../workspace.md). Include source
IDs and supporting excerpts/locations in findings; record incomplete coverage or
source truncation. Never manufacture source names, quotations, or favorable verdicts.

Adapted from BlogForge `generate/claims.py`, with clearer coverage and uncertainty.
