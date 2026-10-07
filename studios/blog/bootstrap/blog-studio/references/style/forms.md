# Choose a useful article form

Blog type describes what the reader needs; writing mode describes what the author
wants now (outline, draft, interview or edit). Keep these choices independent.
Reuse a saved type or infer it from the request and supplied outline. These are
scaffolds, not mandatory headings. A passage polish does not trigger selection.

## Intake choice

For an open-ended software-product start with an unresolved type, offer once:

> What kind of post are you aiming for: a product announcement, tutorial,
> architecture explanation, performance deep dive, comparison, or customer/engineering
> story? If you're unsure, tell me what readers should learn or do.

Use short natural labels; no forced menu if intent is already clear. Recommend
a type from the reader's goal when asked. Permit a deliberate hybrid or another
form; choose a primary reader purpose to keep its structure coherent. Missing
benchmark/customer evidence is a gap to surface, not permission to invent it.

## Selected form and guidance

Use only the chosen row and references relevant to actual content. A referenced
check describes coverage when requested; it does not authorize every review.

| Blog type | Useful progression | Conditional guidance/review focus |
| --- | --- | --- |
| Product or feature announcement | Reader problem → what changed → example → availability/limits → next step | [Software claims](software.md): delivered behavior, version/edition and concrete benefit |
| Tutorial | Outcome → prerequisites → steps → verification → cleanup → further learning | [Practical examples](examples.md): environment, runnable steps and actual test status |
| Architecture or concept explanation | Question → mental model → mechanism → tradeoffs → example | [Software claims](software.md) when describing a product; [visuals](visuals.md) when a diagram helps |
| Performance deep dive | Hypothesis/question → setup → results → explanation → limitations → reproduction | [Performance evidence](performance.md): comparable baselines, errors, variation and causal limits |
| Comparison or decision guide | Use case → criteria → evidence → tradeoffs → conditional recommendation | [Software claims](software.md); add performance guidance only for measured comparisons |
| Customer or engineering story | Starting situation → constraints → decisions → implementation → observed results → lessons | [Fact check](../modules/blog-fact-check.md) when requested: attributable experience, approved quotes and supported outcomes |

Within a tutorial request, distinguish learning through an exercise from a how-to
for an already competent reader. A how-to can go directly from assumptions to
steps, result checks and recovery. Keep conceptual digressions short and link
optional depth. Explanations do not require code or exhaustive API reference.

## Carry the selection forward

Save the type and reader takeaway in the existing brief, alongside explicit
constraints, e.g. `Blog type: Architecture explanation; purpose: explain the
tradeoff; avoid: step-by-step setup.` No new mode or runtime schema is required.
If inferred, note that it is a working choice and continue; no extra approval.
An imported draft can retain its existing form without being rewritten to fit a row.

Outline and draft from that saved purpose. A requested shape review checks whether
the article delivers it, not whether every suggested heading appears. A requested
factual review checks the relevant evidence; proofreading preserves author voice.
If the author changes type, save the updated brief and follow existing review
freshness rules. A type change does not by itself authorize a whole-draft rewrite.
Outline-only still stops at the outline. Resume reuses the type without re-asking.

The learning/task/explanation distinction is adapted from Diátaxis. Announcement,
comparison and story structures are Blog Studio editorial choices; the optional
[source map](sources.md) records their basis. Team rules, author voice and technical
evidence remain separate inputs with existing scope and pin semantics.
