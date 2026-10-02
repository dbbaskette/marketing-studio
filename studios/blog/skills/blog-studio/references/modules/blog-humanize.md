# Humanization capability

Keep private inputs in the user's existing harness and selected private hub.
Apply [data boundaries](../privacy.md) before research, media, or document
posting; upstream suggestions do not authorize external disclosure.

**Input:** draft, author voice, desired light/medium/strong intensity, selected scope.
**Output:** located prose suggestions or requested edits with factual preservation checks.

Light focuses on flow and formulaic prose; medium can address voice/point of view;
strong can preserve appropriate lived-in texture. For routine feedback, locate
repeated paragraph entrances, monotonous rhythm, generic stance, or mannered
phrasing; distinguish deliberate voice from defects. Read the [four-lens rubric](../blogforge/voice/assets/humanize/lenses.md)
only for a requested deep lens-by-lens pass. Treat it as editorial guidance, not detector evasion or
proof of authorship. Never invent an opinion, experience, hesitation, typo, or
anecdote to make a passage seem human.

Preserve names, facts, numbers, links, and quotations. When applying edits, run the `preserve` operation
in `scripts/text_checks.py` for obvious changes and separately read for semantic
changes; token preservation alone cannot establish factual equivalence. The
upstream opening exemption applies only if the current workflow intentionally
locks an opening. Otherwise improve it when the author requested that change.

Offer target, rewrite, and reason for feedback mode; directly apply already
requested edits with a snapshot. Save requested review results as `humanization`.
Recheck affected evidence after a change, without a mandatory unrelated review.

Adapted from BlogForge's humanization lenses and changed-fact flags.
