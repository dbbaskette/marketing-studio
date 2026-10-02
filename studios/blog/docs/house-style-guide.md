# Blog Studio house style

The [house guide](../skills/blog-studio/references/style/house.md) supplies small,
shared defaults for software product blogs. It preserves author voice, imported
dialect and selected team preferences. It is conditional writing guidance, not
another application, mandatory intake form or publication approval step.

## Framework and loading

1. Entry/module link selects the house guide for software-product outlining,
   drafting, editing or a requested style review. Setup and source/voice intake
   do not load it.
2. The guide covers reader purpose, voice, mechanics, product relevance and shape.
   Load article forms, software claims, practical examples, performance evidence
   or visual explanations only when the task needs them. Reuse unchanged files.
3. The [source map](../skills/blog-studio/references/style/sources.md) records
   research, attribution and deliberate house choices. Load it for maintenance
   or provenance questions, not ordinary drafting. No live web fetch is required
   to use the guide. Product fact verification still follows the research policy.

The initial research covered Google, Microsoft, GitLab, Diátaxis and Brendan
Gregg. Targeted follow-up addressed feature availability, heading conventions,
accessible diagrams and adapting external style guides to a local organization.
Instructions are an original synthesis rather than copied manuals. External
vendor process, keyword quotas and absolute word bans were not imported.

## Use it in chat

> Draft a software product blog using our house style and my saved voice. Explain
> the feature's mechanism and limitations. Use only the supplied sources.

> Give this post a house-style review. Return located suggestions; don't rewrite it.

> Outline a how-to for the supplied configuration. Keep the team's terminology
> and stop at the outline. Identify prerequisites and missing verification evidence.

Style review uses the existing `proofread` result; software/performance evidence
uses `factual-support`. Coverage and incomplete evidence remain explicit. The
framework does not add a competing reviewer or claim any code was executed.

## Optional blog-type selector

At an open-ended software-blog start, Blog Studio offers announcement, tutorial,
architecture/concept explanation, performance deep dive, comparison/decision guide,
or customer/engineering story. Clear requests skip the menu. “Not sure” can be
resolved from what the reader should learn or do; deliberate hybrids are allowed.

Type is independent of outline/draft/interview/edit mode and is saved in the brief.
Later outlining, drafting, interviewing and shape review reuse it. Tutorial/how-to
needs receive different levels of explanation. No choice expands the requested
stop point, creates evidence, or starts all review checks automatically.

The framework keeps four inputs distinct:

| Input | Responsibility |
| --- | --- |
| Selected team rules in the Hub | Terminology, product naming, capitalization, citations and CTA preferences |
| Author voice profile | Personality, rhythm, preferred depth and explanation style |
| Selected blog type | Reader purpose, structure and applicable references |
| Existing technical checks | Evidence, versions, examples, availability and claim accuracy |

## Team customization

Keep shared preferences in the Team Hub's existing scoped `rule` records and
attach the selected revisions as article context. Record a one-off exception in
the brief or article memory. No team records are created merely by loading the
guide. A useful preference contains a narrow key, actual rule, applicability and
examples or exceptions, for example:

```text
Key: style.headings
Scope: project (the selected publication)
Rule: Use sentence case for new headings; retain official product spelling.
Exception: Preserve supplied campaign titles unless a title revision is requested.
```

Follow [team memory](../skills/blog-studio/references/hub/memory.md) for saves,
conflicts and adoption. Current user instructions and selected preferences take
precedence over generic defaults. A profile supplies personality and rhythm;
style guidance never invents experience, changes the author's stance or overrides
accurate technical language.

## Updates and verification

The house guide itself is guidance-only. This release also includes Google
formatting helpers, which require the bundled 1.5.0 runtime. New tasks fetch
it after publication through the ordinary guidance update. Existing articles
retain their pinned guidance and team-rule revisions until adoption is requested.
The full offline archive includes all references; that does not load them all into
context. Update the installer once to use the Google formatting helpers.

Token estimates are unique Unicode characters divided by four, rounded per file;
not tokenizer counts or billed usage. Conditional costs are recorded under
`house_style_operations` in the [inventory](estimates/blog-studio-token-inventory.json).
They exclude the existing writing route, author data and output. A task using
several extensions counts their union, including the house guide only once.

Measured initial costs: the core guide adds about **623 tokens**; core plus
software claims adds **1,177**; practical and performance posts add **1,661** and
**1,675**, respectively, before any separately needed form or visual reference.
The source map is optional maintenance material. See the dated
[roadmap table](progressive-disclosure-roadmap.md#house-style-disclosure--october-2-2026).

## Validation — 2026-10-02

All 141 existing tests passed in Tart with Python 3.13.16 (84.405 seconds)
for the initial house-guide slice. The subsequent selector changes only guidance;
the runtime and test source are unchanged, so that regression evidence is reused.
The skill validator, authored reference links, immutable-source provenance,
token inventory, portable archive checksum/source equality and whitespace checks
passed. That initial guidance slice did not change the runtime; see the Google round-trip
validation for the subsequent 1.5 runtime changes.

Manual instruction walkthroughs covered these boundaries; they were not live
model-generated article tests:

| Scenario | Inspected behavior |
| --- | --- |
| Feature announcement with supplied evidence | House + software guidance; form only if unresolved; no mandatory benchmark or sales CTA |
| Ambiguous new software blog | Offer the six types once; allow uncertainty/custom forms; save purpose in the brief |
| Resuming a saved article | Reuse its saved type; no repeated intake menu |
| Outline-only tutorial | House + selected form/example guidance; prerequisites and evidence gaps; stop remains outline |
| Unsupported speedup | Performance lens feeds the existing factual check; no invented measurement or execution |
| Small polish with a saved voice/dialect | Scope and selected voice preserved; no automatic rewrite or web research |
| Changed team preference on an existing article | Existing context/guidance pins retained; deliberate adoption through current memory controls |

Behavioral effectiveness in real writing remains an author/harness pilot; these
checks establish routing, packaging, preservation and regression behavior.
