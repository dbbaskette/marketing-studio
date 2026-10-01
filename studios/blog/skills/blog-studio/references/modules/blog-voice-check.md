# Voice and repetition check capability

**Input:** manuscript, author rules and guide, review scope.
**Output:** located findings and targeted repairs, with recheck results.

Separate deterministic matches from editorial judgments. Check explicit author
restrictions, repeated distinctive phrases, near-duplicate paragraphs, and echoed
section entrances. A useful finding names the passage, rule/reason, proposed fix,
and any uncertainty. Generic vocabulary alone does not establish AI authorship.

Use `scripts/text_checks.py` through [workspace](../workspace.md) for mechanical
rule and repetition findings. Read the [pattern reference](../blogforge/voice/assets/ai-tells/patterns.md)
only for a requested deeper editorial review. The bundled word/phrase lists are
optional heuristics, not automatic author restrictions. Punctuation bans apply
only when explicitly selected; preserve code blocks, inline code, URLs, and quotes.

Repair only selected violations, preserve meaning/voice, and recheck the same
rules after the repair. Do not mechanically replace substantive terminology or
alter facts to satisfy a style rule. Save requested review results as `proofread`.

Adapted from BlogForge voice lint, enforcement, and draft repetition detection.
