# House-style source map

Research reviewed 2026-10-02. This is a maintenance reference, not a reading list
for each article. The house guide is an authored synthesis; no external style
manual has been vendored. Source recommendations are editorial guidance, not
experimental proof of conversion or search-ranking effects.

| Framework concern | Primary reference | Adopted guidance |
| --- | --- | --- |
| Audience | [Google technical writing: audience](https://developers.google.com/tech-writing/one/audience) | Match role, prior knowledge and desired task. |
| Tone | [Google developer voice](https://developers.google.com/style/tone) | Conversational precision; avoid empty language and trivializing difficulty. |
| Mechanics | [Microsoft style and voice](https://learn.microsoft.com/en-us/style-guide/top-10-tips-style-voice) and [Google headings](https://developers.google.com/style/headings) | Front-load useful information; descriptive, sentence-case headings. |
| Blog framing | [GitLab blog style](https://handbook.gitlab.com/handbook/marketing/product-and-technical-marketing/content/editorial-team/) | Explain reader relevance and connect product detail to a concrete problem. |
| Article purpose | [Diátaxis primer](https://www.diataxis.fr/start-here/) | Separate learning, task completion, explanation and reference needs. |
| Availability | [GitLab product availability](https://docs.gitlab.com/development/documentation/styleguide/availability_details/) | Make relevant version, edition, deployment and feature state explicit. |
| Examples | [Google code samples](https://developers.google.com/style/code-samples) | Introduce samples and distinguish incomplete code from runnable examples. |
| Measurements | [Brendan Gregg's benchmarking checklist](https://www.brendangregg.com/blog/2018-06-30/benchmarking-checklist.html) | Examine tuning, limits, errors, reproducibility and workload relevance. |
| Visual clarity | [Google images](https://developers.google.com/style/images) | Use informative alt text and nearby explanations of complex visuals. |
| Search/length | [Google people-first content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) | Satisfy the reader's purpose; there is no preferred Google word count. |
| Local adaptation | [Write the Docs: style guides](https://www.writethedocs.org/guide/writing/style-guides/) | Use a maintained style guide for consistency, adapted to the organization. |

Blog Studio choices: US English only as an unspecified new-copy default; preserve
imported dialect and author voice; optional announcement/comparison/story scaffolds;
no universal word or sentence quotas; existing review and pin semantics. These
are our decisions, not claims of agreement across every cited guide. In particular,
we do not adopt absolute “shorter is always better,” bans on starting with “this,”
or vendor-specific formatting, tools, terminology and approval processes.

## Maintain the guide

Start with a demonstrated writing problem. Map it to one concern above, inspect
relevant primary guidance, and add the smallest useful instruction/example to the
appropriate file. Record changed source dates and rationale here. Keep essential
rules self-contained so ordinary use needs no web fetch. Recheck links when
maintaining; external pages can change and do not override user instructions.

Keep common guidance small; add specialized details only to their selected leaf.
Measure unique file loads, not the sum of every leaf for every post. Behavior
review should cover an announcement, a procedure, a performance claim, a constrained
passage edit and a conflicting/pinned team preference. Label manual walkthroughs
separately from live harness tests.
