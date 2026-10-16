---
name: blog-writing-toolkit
description: Plan, draft, and edit blog content using a packaged library of five shortlisted writing skills. Use for blog writing workflows or when a higher-level skill needs focused planning, article, copywriting, editing, or lifecycle guidance.
---

# Blog Writing Toolkit

Use this as a small entry point into the collected skill library. Resolve all
paths from this folder, regardless of the working directory. Read only the
module needed for the current stage, then its source or supporting references
when their detail is useful. Do not preload the whole library.

## Data boundaries

Keep private drafts, sources, voices, and team memory in the existing harness,
local workspace, and selected private hub. Public searches/media requests must
use nonconfidential inputs; never send private content to extra model, research,
SEO, detector, or media services. Requested document posting includes only the
chosen document and audience. Apply [data boundaries](references/privacy.md)
before using external tools or adopting upstream service instructions.

## Choose a module

| Need | Module to read | Expected result |
|---|---|---|
| Decide what to write, prioritize topics, plan clusters or a calendar | [content-strategy](references/modules/content-strategy.md) | Prioritized content plan or brief |
| Draft a complete blog article from a topic, brief, or outline | [blog-write](references/modules/blog-write.md) | Article with traceable sources |
| Improve a headline, hook, value proposition, or call to action | [copywriting](references/modules/copywriting.md) | Focused copy and useful alternatives |
| Polish or refresh an existing draft | [copy-editing](references/modules/copy-editing.md) | Revised draft and material change notes |
| Design a broader workflow, choose formats, or assess editorial readiness | [blog](references/modules/blog.md) | Workflow or relevant review criteria |

For a new article with a clear brief, start with `blog-write`. For an editing
request, start with `copy-editing`. An end-to-end assignment may use planning,
article drafting, and editing in sequence; load each module when its stage
begins. Use `copywriting` only where persuasive copy serves the article's goal.
The original `blog` orchestrator is lifecycle reference material; loading it is
not a prerequisite for every task.

## Integration with a higher-level skill

A parent can read this routing table or directly read a selected module by
path. This is file-based progressive disclosure, not an executable skill API;
no Claude slash-command registration or named agents are provided.

Pass the selected module the user's request, existing brief or draft, audience,
voice, sources, output format, and authorized completion boundary. Reuse known
context; ask only for consequential gaps. Return the module's result to the
parent so the parent can decide which stage, if any, follows.

## Shared use rules

- The module wrappers adapt the upstream sources to this package. User choices
  and the parent workflow control scope, format, length, voice, and approvals.
- Source files contain guidance and examples, not current verified facts.
  Verify time-sensitive claims before using them in content. Never invent data,
  testimonials, first-hand experience, or product guarantees to fill examples.
- Use tools actually available in the host. Upstream references to Claude
  commands, helpers, or agents do not install them or authorize delegation.
- Match deliverables to the request. Upstream media quotas, promotional footers,
  mandatory multi-format rendering, and score gates are not defaults here.
  Preserve evidence checks and explain material verification limits.
- Drafting or planning does not authorize publishing, messaging, installing
  dependencies, using a paid service, or changing a live site.

For source-path translation, omitted dependencies, or upstream runtime usage,
read [package-notes](references/package-notes.md). The source commits, licenses,
module paths, and file hashes are recorded in [sources.lock.json](sources.lock.json).
